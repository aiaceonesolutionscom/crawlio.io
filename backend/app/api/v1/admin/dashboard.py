from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin_deps import require_super_admin
from app.db.models.platform_admin import PlatformAdmin
from app.db.session import get_session
from app.schemas.admin import AdminDashboardOverview
from app.services import admin_dashboard_service
from app.services.crawlers.base import source_tracker

router = APIRouter(prefix="/dashboard", tags=["admin:dashboard"])


@router.get("/overview", response_model=AdminDashboardOverview)
async def get_dashboard_overview(
    admin: Annotated[PlatformAdmin, Depends(require_super_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    return await admin_dashboard_service.compute_overview(session)


@router.get("/sources")
async def get_source_health(
    admin: Annotated[PlatformAdmin, Depends(require_super_admin)],
):
    """Per-crawler-source reliability stats (rolling window) so an admin can see
    which lead sources are healthy, degraded or failing right now."""
    return {
        "sources": source_tracker.all_stats(),
        "unhealthy_sources": source_tracker.unhealthy(min_rate=0.3, min_samples=5),
    }


@router.post("/sources/recover")
async def recover_sources(
    admin: Annotated[PlatformAdmin, Depends(require_super_admin)],
):
    """Reset circuit breakers and proxy suspensions so blocked sources get an
    immediate retry instead of waiting out their cooldown. Also clears the
    reliability stats window so a recovered source starts fresh."""
    from app.services.crawlers import bing_maps_crawler, bizdata_crawler, directory_scraper, maps_crawler

    for breaker in (
        maps_crawler._breaker,
        bing_maps_crawler._breaker,
        bizdata_crawler._breaker,
        directory_scraper._breaker,
    ):
        breaker._consecutive_failures = 0
        breaker._blocked_until = 0.0
    for rotator in (
        maps_crawler._proxy_rotator,
        directory_scraper._proxy_rotator,
    ):
        rotator.clear()
    return {"status": "recovered", "sources": source_tracker.all_stats()}
