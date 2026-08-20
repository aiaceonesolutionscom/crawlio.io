import asyncio
import logging
import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

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
from app.services.discovery.discovery_safety import (
    discovery_breaker,
    enforce_minimum_results,
    filter_incomplete_leads,
    recovery_trigger,
)
from app.services.enrichment import enrichment_jobs
from app.services.lead.lead_service import DuplicateLeadError, create_lead, find_existing_emails_and_phones
from app.services.workspace.quota_service import count_discovery_leads_today
from app.workers.tasks_enrichment import _enrich_batch_async

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/leads/discover", tags=["lead-discovery"])

# A cushion for validation attrition (some raw candidates won't survive MX/phone
# checks), not a target to actually hit — discovery_service's own "are we still
# short?" checks (nearby-city fallback, Overpass radius escalation) compare
# against whatever gets passed as `limit`, so keep this modest. A larger
# multiplier just makes the backend chase leads that get discarded by the
# results[:limit] truncation below anyway.
FREE_TIER_OVERFETCH_MULTIPLIER = 1.2
# Minimum acceptable results before we consider a search degraded
MINIMUM_ACCEPTABLE_RESULTS = 5


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

    Phase 1 (this request, fast): kick off a background crawl of the three free
    open-source sources — Google Maps (primary), OSM/Overpass, and free Pakistan
    directories — and return immediately with a `search_id`. The crawl itself
    takes minutes (real browser visits, page timeouts, throttling), so it MUST
    NOT run inside the request handler: one slow crawl would block the whole API.
    The client polls GET /leads/discover/{search_id} for live progress.
    Phase 2 (background): each lead's own website is scraped to fill remaining
    email/social gaps; the same poll endpoint reflects enrichment progress.
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
    #
    # SAFETY LAYER: CacheQualityValidator integrated in get_cached() will reject
    # stale/partial entries (e.g. 1-result caches from yesterday's bug)
    cache_hit = await discovery_cache_service.get_cached(
        session, payload.niche, payload.city, payload.country, requested_limit=limit
    )
    if cache_hit:
        cached_items, cached_at = cache_hit
        # SAFETY CHECK: Even with cache hit, verify minimum threshold
        if len(cached_items) >= limit:
            cached_at_str = cached_at.isoformat() if cached_at else None
            sliced = [dict(r) for r in cached_items[:limit]]
            await _mark_already_in_workspace(session, workspace.id, sliced)

            # SAFETY LAYER: Filter incomplete leads before serving from cache
            sliced = filter_incomplete_leads(sliced)

            items = [
                DiscoveredLead(**{**r, "cache_hit": True, "cached_at": cached_at_str})
                for r in sliced
            ]

            # SAFETY LAYER: Circuit breaker evaluation
            is_good, _ = discovery_breaker.evaluate_search(limit, len(items))

            return DiscoverResponse(
                items=items, total=len(items), limit=limit, enhanced=enhanced,
                daily_limit=daily_limit, remaining_today=remaining_today, search_id=None,
            )
        else:
            logger.info(
                "Cache hit but under-delivered (%d < %d), proceeding to fresh discovery",
                len(cached_items), limit,
            )

    # SAFETY LAYER: Check if circuit breaker is already tripped
    if discovery_breaker.is_degraded:
        logger.warning(
            "Discovery system is degraded (consecutive failures: %d). "
            "Proceeding with fresh discovery but monitoring closely.",
            discovery_breaker.consecutive_failures,
        )

    meta = {
        "niche": payload.niche,
        "city": payload.city,
        "country": country_name,
        "country_code": payload.country,
        "workspace_id": workspace.id,
        "plan": workspace.plan,
        "use_browser": enhanced,
        "use_ai": enhanced,
        "use_google_maps": True,
    }

    search_id = str(uuid.uuid4())
    await enrichment_jobs.create_enrichment_job(search_id, [], meta)
    task_session_factory = async_sessionmaker(session.bind, expire_on_commit=False)
    asyncio.create_task(
        _discover_in_background(
            search_id, payload, workspace, country_name, limit, fetch_limit, enhanced,
            session_factory=task_session_factory,
        )
    )
    return DiscoverResponse(
        items=[], total=0, limit=limit, enhanced=enhanced,
        daily_limit=daily_limit, remaining_today=remaining_today, search_id=search_id,
        source_counts={},
    )


async def _discover_in_background(
    search_id: str,
    payload: DiscoverRequest,
    workspace: Workspace,
    country_name: str,
    limit: int,
    fetch_limit: int,
    enhanced: bool,
    session_factory: Optional[async_sessionmaker] = None,
) -> None:
    """Run the crawl + enrichment off the request path and publish progress into
    the job store, which the polling status endpoint reads. `session_factory`
    defaults to the app-wide maker; callers pass the request engine's own maker
    so tests (in-memory DB) and multi-engine setups stay consistent."""
    session_factory = session_factory or async_session_maker
    counts: dict[str, int] = {}
    try:
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
        logger.warning("Background discovery unavailable for %s: %s", search_id, exc)
        await enrichment_jobs.fail_job(search_id, str(exc))
        return
    except Exception as exc:
        logger.exception("Background discovery failed for %s", search_id)
        await enrichment_jobs.fail_job(search_id, str(exc)[:200])
        return

    # SAFETY LAYER: Evaluate discovery quality via circuit breaker
    is_good, quality_reason = discovery_breaker.evaluate_search(
        requested_limit=fetch_limit,
        actual_results=len(results),
        source_counts=counts,
    )

    if not is_good:
        logger.warning(
            "Discovery quality below threshold for search %s: %s "
            "(results=%d, limit=%d, sources=%s)",
            search_id, quality_reason, len(results), fetch_limit, counts,
        )

        # SAFETY LAYER: Check if auto-recovery should be triggered
        if discovery_breaker.consecutive_failures >= discovery_breaker.failure_threshold:
            if await recovery_trigger.should_trigger(discovery_breaker.consecutive_failures):
                logger.error(
                    "Triggering auto-recovery for search %s: %s",
                    search_id, quality_reason,
                )
                try:
                    report = await recovery_trigger.trigger_recovery(
                        reason=quality_reason,
                        session_factory=session_factory,
                    )
                    logger.info("Auto-recovery report: %s", report)
                except Exception as recovery_exc:
                    logger.error("Auto-recovery failed: %s", recovery_exc)

    # SAFETY LAYER: Enforce minimum results threshold
    results = enforce_minimum_results(results, MINIMUM_ACCEPTABLE_RESULTS)

    # SAFETY LAYER: Filter incomplete leads before caching/display
    results = filter_incomplete_leads(results)

    results.sort(key=lambda r: sum(bool(r.get(f)) for f in ("phone", "email", "website")), reverse=True)
    results = results[:limit]

    # Update circuit breaker with final result count
    final_is_good, _ = discovery_breaker.evaluate_search(limit, len(results), counts)
    if final_is_good:
        logger.info(
            "Discovery quality validated for search %s: %d/%d results, %d sources active",
            search_id, len(results), limit, sum(1 for v in counts.values() if v > 0),
        )

    job = await enrichment_jobs.get_enrichment_job(search_id) or {"search_id": search_id}
    job["items"] = results
    job["status"] = "done" if not results else "in_progress"
    job["source_counts"] = counts
    await enrichment_jobs.save_job(search_id, job)

    async with session_factory() as db:
        await discovery_cache_service.upsert_cache(
            db, payload.niche, payload.city, payload.country,
            niche_display=payload.niche, city_display=payload.city, country_display=country_name,
            items=results,
        )
        await _mark_already_in_workspace(db, workspace.id, results)

    if results:
        try:
            await _enrich_batch_async(
                search_id, payload.city, country_name, payload.country, enhanced, enhanced, True
            )
        except Exception:
            logger.exception("Background enrichment failed for %s", search_id)


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
    existing_emails = set()
    existing_phones = set()
    if emails or phones:
        existing_emails, existing_phones = await find_existing_emails_and_phones(
            session, workspace_id, emails, phones
        )
    for r in results:
        email = (r.get("email") or "").lower()
        phone = r.get("phone") or ""
        r["already_in_workspace"] = bool(
            (email and email in existing_emails) or (phone and phone in existing_phones)
        )


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
