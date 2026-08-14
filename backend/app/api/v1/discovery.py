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
from app.services.discovery import discovery_cache_service, discovery_service, geo_service
from app.services.enrichment import enrichment_jobs, enrichment_pipeline
from app.services.lead.lead_service import DuplicateLeadError, create_lead, find_existing_emails_and_phones

from app.services.workspace.quota_service import count_discovery_leads_today

from app.workers.tasks_enrichment import enrich_discovered_batch

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/leads/discover", tags=["lead-discovery"])

# The crawlers are free (no per-call cost), so the free tier can afford to enrich
# this many candidates. Also the inline-enrichment cap when the worker is down.
MAX_SCRAPED_PER_SEARCH = 60
# A cushion for validation attrition (some raw candidates won't survive MX/phone
# checks), not a target to actually hit — discovery_service's own "are we still
# short?" checks (nearby-city fallback, Overpass radius escalation) compare
# against whatever gets passed as `limit`, so keep this modest. A larger
# multiplier just makes the backend chase leads that get discarded by the
# results[:limit] truncation below anyway.
FREE_TIER_OVERFETCH_MULTIPLIER = 2
INLINE_ENRICH_CAP = MAX_SCRAPED_PER_SEARCH


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

    Phase 1 (this request, fast): three free open-source crawlers run in parallel
    — Google Maps (primary), OSM/Overpass, and free Pakistan directories — and
    return real, contact-validated leads immediately with a `search_id`.
    Phase 2 (background worker): each lead's own website is scraped to fill
    remaining email/social gaps, and the client polls
    GET /leads/discover/{search_id} for live progress. If no worker is available
    the first `INLINE_ENRICH_CAP` leads are enriched synchronously instead, so
    the feature never returns raw partial data.
    """
    plan_cap = DISCOVERY_LIMITS.get(workspace.plan, 50)
    limit = min(payload.limit, plan_cap) if payload.limit else plan_cap
    limit = max(limit, 1)

    enhanced = "lead_discovery_enhanced" in PLAN_CAPABILITIES.get(workspace.plan, set())
    fetch_limit = limit if enhanced else min(limit * FREE_TIER_OVERFETCH_MULTIPLIER, 100)

    country_name = geo_service.country_name_for_code(payload.country) or payload.country

    daily_limit = DAILY_DISCOVERY_IMPORT_LIMITS.get(workspace.plan, 50)
    used_today = await count_discovery_leads_today(session, workspace.id)
    remaining_today = max(daily_limit - used_today, 0)

    # Shared, global cache (not workspace-scoped) — the same niche+city+country
    # search from any workspace reuses a prior validated scrape instead of
    # re-hitting Google Maps/OSM/directories, which is what makes serving many
    # workspaces' worth of daily volume affordable on free infrastructure.
    cache_hit = await discovery_cache_service.get_cached(session, payload.niche, payload.city, payload.country)
    if cache_hit:
        cached_items, cached_at = cache_hit
        if len(cached_items) >= limit:
            cached_at_str = cached_at.isoformat() if cached_at else None
            sliced = [dict(r) for r in cached_items[:limit]]
            await _mark_already_in_workspace(session, workspace.id, sliced)
            items = [
                DiscoveredLead(**{**r, "cache_hit": True, "cached_at": cached_at_str})
                for r in sliced
            ]
            return DiscoverResponse(
                items=items, total=len(items), limit=limit, enhanced=enhanced,
                daily_limit=daily_limit, remaining_today=remaining_today, search_id=None,
            )

    try:
        counts: dict[str, int] = {}
        results = await discovery_service.discover_businesses(
            payload.niche,
            payload.city,
            country_name,
            country_code=payload.country,
            limit=fetch_limit,
            enrich_candidates=enhanced,
            source_counts=counts,
        )
    except discovery_service.DiscoveryUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    results.sort(key=lambda r: sum(bool(r.get(f)) for f in ("phone", "email", "website")), reverse=True)
    results = results[:limit]

    meta = {
        "niche": payload.niche,
        "city": payload.city,
        "country": country_name,
        "country_code": payload.country,
        "workspace_id": workspace.id,
        "plan": workspace.plan,
        "use_browser": enhanced,
        "use_ai": enhanced,
        "use_google_maps": enhanced,
    }

    search_id = str(uuid.uuid4())
    stored = await enrichment_jobs.create_enrichment_job(search_id, results, meta)
    if stored:
        try:
            enrich_discovered_batch.delay(
                search_id, payload.city, country_name, payload.country, enhanced, enhanced, enhanced
            )
        except Exception as exc:
            logger.warning("Could not dispatch background enrichment for %s: %s", search_id, exc)
            results = await _inline_enrich(search_id, results, meta, cap=min(limit, MAX_SCRAPED_PER_SEARCH))
    else:
        logger.info("Enrichment store unavailable; enriching %s leads inline", len(results))
        search_id = None
        results = await _inline_enrich(search_id or "", results, meta, cap=min(limit, MAX_SCRAPED_PER_SEARCH))

    # Warm the cache now with what we have (fuller when Redis was down and
    # enrichment ran inline above); if background enrichment is still pending,
    # enrich_discovered_batch refreshes this same row once it finishes.
    await discovery_cache_service.upsert_cache(
        session, payload.niche, payload.city, payload.country,
        niche_display=payload.niche, city_display=payload.city, country_display=country_name,
        items=results,
    )

    await _mark_already_in_workspace(session, workspace.id, results)
    items = [DiscoveredLead(**r) for r in results]
    return DiscoverResponse(
        items=items, total=len(items), limit=limit, enhanced=enhanced,
        daily_limit=daily_limit, remaining_today=remaining_today, search_id=search_id,
        source_counts=counts,
    )


@router.get("/{search_id}", response_model=DiscoveryStatusResponse)
async def discover_status(
    search_id: str,
    workspace: Annotated[Workspace, Depends(get_current_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    """Live enrichment status for an in-flight discovery search."""
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


async def _mark_already_in_workspace(session: AsyncSession, workspace_id: str, results: list[dict]) -> None:
    """Flags each result already present in the requesting workspace's CRM
    (by email/phone, same rule as import-time dedup) — one batch query, not
    one per result. Makes a repeat search show what's actually new instead of
    looking like a frozen re-run of the same list, whether the results came
    from a fresh scrape or the shared cache."""
    emails = [r.get("email") for r in results if r.get("email")]
    phones = [r.get("phone") for r in results if r.get("phone")]
    if not emails and not phones:
        return
    existing_emails, existing_phones = await find_existing_emails_and_phones(session, workspace_id, emails, phones)
    if not existing_emails and not existing_phones:
        return
    for r in results:
        email = (r.get("email") or "").lower()
        phone = r.get("phone") or ""
        if (email and email in existing_emails) or (phone and phone in existing_phones):
            r["already_in_workspace"] = True


async def _inline_enrich(search_id: str, results: list[dict], meta: dict, cap: int = INLINE_ENRICH_CAP) -> list[dict]:
    """Best-effort synchronous enrichment used when the background worker can't
    run (Redis/Celery unavailable). Bounded to keep request latency sane.

    Uses enrich_items_batch (not enrich_item in a loop) — a headless-browser
    launch is the expensive part of enrichment, so funneling every lead in the
    batch through ONE shared browser instead of one launch per lead is what
    actually keeps this fast when the worker is down."""
    batch = results[:cap]
    try:
        enriched = await enrichment_pipeline.enrich_items_batch(
            batch,
            city=meta.get("city", ""),
            country=meta.get("country", ""),
            country_code=meta.get("country_code"),
            use_browser=bool(meta.get("use_browser", False)),
            use_ai=bool(meta.get("use_ai", False)),
            use_google_maps=bool(meta.get("use_google_maps", False)),
        )
    except Exception as exc:
        logger.warning("Inline batch enrichment failed for %s: %s", search_id, exc)
        return results
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
                        "enrichment_source", "last_enriched_at",
                        "rating", "review_count", "category", "plus_code"):
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
