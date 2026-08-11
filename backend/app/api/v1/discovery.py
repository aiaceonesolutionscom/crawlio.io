import asyncio
import logging
import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_workspace, require_plan
from app.core.plans import DAILY_DISCOVERY_IMPORT_LIMITS, DISCOVERY_LIMITS, PLAN_CAPABILITIES
from app.data.niches import SUGGESTED_NICHES
from app.db.session import get_session
from app.db.models.workspace import Workspace
from app.schemas.discovery import (
    DiscoveredLead,
    DiscoverRequest,
    DiscoverResponse,
    DiscoveryImportRequest,
    DiscoveryImportResult,
    DiscoveryImportSkip,
    DiscoveryStatusResponse,
)
from app.schemas.lead import LeadCreate, lead_to_read
from app.services import (
    discovery_service,
    enrichment_jobs,
    enrichment_pipeline,
    geo_service,
)
from app.services.lead_service import DuplicateLeadError, create_lead
from app.services.quota_service import count_discovery_leads_today
from app.workers.tasks_enrichment import enrich_discovered_batch

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/leads/discover", tags=["lead-discovery"])

# How many results get a Tavily website-URL lookup per search (Pro+). Bounded
# to keep latency and API usage predictable — Tavily is a paid, rate-limited
# external call per lead.
MAX_TAVILY_ENRICHED_PER_SEARCH = 15
# Website-content scraping is free (no API, no per-call cost), so free tier can
# afford to enrich more candidates — this matters because free tier's strict
# "no blanks" filter drops anything scraping doesn't complete.
MAX_SCRAPED_PER_SEARCH = 60
# Pro+ only: real headless-browser scraping is far heavier per-site than a
# plain HTTP GET (page render, multiple subpath navigations), so this is kept
# well below the plain-HTTP cap to keep total search latency reasonable.
MAX_BROWSER_SCRAPED_PER_SEARCH = 25
# Free tier's overfetch multiplier. Kept so free search still pulls plenty of
# candidates before the completeness sort, even though partial leads are now kept.
FREE_TIER_OVERFETCH_MULTIPLIER = 6
# If the background worker isn't reachable (Redis down), enrich this many leads
# inline so the search still returns useful data instead of raw partial rows.
INLINE_ENRICH_CAP = 15


@router.get("/niches")
async def list_niche_suggestions(
    workspace: Annotated[Workspace, Depends(get_current_workspace)],
    q: Optional[str] = Query(default=None),
):
    if not q:
        return {"items": SUGGESTED_NICHES}
    matches = [n for n in SUGGESTED_NICHES if q.lower() in n.lower()]
    return {"items": matches}


@router.post("", response_model=DiscoverResponse)
async def discover(
    payload: DiscoverRequest,
    workspace: Annotated[Workspace, Depends(require_plan("lead_discovery"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    """Two-phase lead discovery.

    Phase 1 (this request, fast): a web-based URL finder agent (Tavily +
    DuckDuckGo) pulls candidate businesses for the niche+city — their own
    websites, plus website-less businesses surfaced through directory pages —
    and returns them immediately with a `search_id`. Phase 2 (background
    worker): each candidate gets enriched — own-website scrape, contact
    search, AI disambiguation, social profiles — and the client polls
    GET /leads/discover/{search_id} for live progress. If no worker is
    available the first `INLINE_ENRICH_CAP` leads are enriched synchronously
    instead, so the feature never returns raw partial data.
    """
    plan_cap = DISCOVERY_LIMITS.get(workspace.plan, 50)
    limit = min(payload.limit, plan_cap) if payload.limit else plan_cap
    limit = max(limit, 1)

    enhanced = "lead_discovery_enhanced" in PLAN_CAPABILITIES.get(workspace.plan, set())
    fetch_limit = limit if enhanced else min(limit * FREE_TIER_OVERFETCH_MULTIPLIER, 200)

    country_name = geo_service.country_name_for_code(payload.country) or payload.country

    try:
        results = await discovery_service.discover_businesses(
            payload.niche, payload.city, country_name, limit=fetch_limit
        )
    except discovery_service.DiscoveryUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    # Partial leads are deliberately kept now (a name+address business is still
    # a real lead the background enrichment can fill in). Sort most-complete-first
    # so the user's requested cap is filled with the most usable candidates.
    results.sort(key=lambda r: sum(bool(r.get(f)) for f in ("phone", "email", "website")), reverse=True)
    results = results[:limit]

    daily_limit = DAILY_DISCOVERY_IMPORT_LIMITS.get(workspace.plan, 50)
    used_today = await count_discovery_leads_today(session, workspace.id)
    remaining_today = max(daily_limit - used_today, 0)

    meta = {
        "niche": payload.niche,
        "city": payload.city,
        "country": country_name,
        "country_code": payload.country,
        "workspace_id": workspace.id,
        "plan": workspace.plan,
        "use_browser": enhanced,
        "use_ai": enhanced,
    }

    search_id = str(uuid.uuid4())
    stored = await enrichment_jobs.create_enrichment_job(search_id, results, meta)
    if stored:
        try:
            enrich_discovered_batch.delay(
                search_id, payload.city, country_name, payload.country, enhanced, enhanced
            )
        except Exception as exc:
            logger.warning("Could not dispatch background enrichment for %s: %s", search_id, exc)
            results = await _inline_enrich(search_id, results, meta)
    else:
        # Redis down — no worker can pick this up; enrich inline so the user
        # still gets contact data back on this request.
        logger.info("Enrichment store unavailable; enriching %s leads inline", len(results))
        search_id = None
        results = await _inline_enrich(search_id or "", results, meta)

    items = [DiscoveredLead(**r) for r in results]
    return DiscoverResponse(
        items=items, total=len(items), limit=limit, enhanced=enhanced,
        daily_limit=daily_limit, remaining_today=remaining_today, search_id=search_id,
    )


@router.get("/{search_id}", response_model=DiscoveryStatusResponse)
async def discover_status(
    search_id: str,
    workspace: Annotated[Workspace, Depends(get_current_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    """Live enrichment status for an in-flight discovery search. Returns the
    leads with their current enrichment_state so the frontend can render
    progressive "enriching → done" updates."""
    job = await enrichment_jobs.get_enrichment_job(search_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search not found or expired")
    if job.get("meta", {}).get("workspace_id") != workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search not found or expired")

    items = [DiscoveredLead(**it) for it in job.get("items", [])]
    return DiscoveryStatusResponse(
        search_id=search_id,
        status=job.get("status", "in_progress"),
        items=items,
    )


async def _inline_enrich(search_id: str, results: list[dict], meta: dict, cap: int = INLINE_ENRICH_CAP) -> list[dict]:
    """Best-effort synchronous enrichment used when the background worker can't
    run (Redis/Celery unavailable). Bounded to keep request latency sane."""
    batch = results[:cap]
    semaphore = asyncio.Semaphore(4)

    async def _work(item: dict) -> dict:
        async with semaphore:
            return await enrichment_pipeline.enrich_item(
                item,
                city=meta.get("city", ""),
                country=meta.get("country", ""),
                country_code=meta.get("country_code"),
                use_browser=bool(meta.get("use_browser", False)),
                use_ai=bool(meta.get("use_ai", False)),
            )

    enriched = await asyncio.gather(*(_work(item) for item in batch), return_exceptions=True)
    for index, outcome in enumerate(enriched):
        if isinstance(outcome, dict) and outcome:
            results[index] = outcome
    return results


@router.post("/import", response_model=DiscoveryImportResult)
async def import_discovered(
    payload: DiscoveryImportRequest,
    workspace: Annotated[Workspace, Depends(require_plan("lead_discovery"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    daily_limit = DAILY_DISCOVERY_IMPORT_LIMITS.get(workspace.plan, 50)
    used_today = await count_discovery_leads_today(session, workspace.id)

    created = []
    skipped = []

    for item in payload.items:
        if used_today + len(created) >= daily_limit:
            skipped.append(DiscoveryImportSkip(name=item.name, reason="daily_limit_reached"))
            continue
        try:
            enriched_meta = {}
            for key in ("description", "hours", "completeness", "enrichment_status",
                        "enrichment_source", "last_enriched_at"):
                value = getattr(item, key, None)
                if value is not None:
                    enriched_meta[key] = value
            lead = await create_lead(
                session,
                workspace,
                LeadCreate(
                    name=item.name,
                    email=item.email,
                    phone=item.phone,
                    website=item.website,
                    address=item.address,
                    lat=item.lat,
                    lon=item.lon,
                    industry=item.industry,
                    social_links=item.social_links or None,
                    lead_metadata=enriched_meta or None,
                    source=f"Lead Discovery ({item.source})",
                ),
            )
            created.append(lead_to_read(lead))
        except DuplicateLeadError:
            skipped.append(DiscoveryImportSkip(name=item.name, reason="duplicate"))
        except HTTPException as exc:
            if exc.status_code == status.HTTP_403_FORBIDDEN:
                skipped.append(DiscoveryImportSkip(name=item.name, reason="quota_exceeded"))
                break
            raise

    return DiscoveryImportResult(created=created, skipped=skipped)
