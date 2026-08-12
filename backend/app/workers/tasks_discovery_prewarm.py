"""Demand-driven background cache pre-warmer.

Refreshes discovery_cache rows *before* they expire, spread gently across the
day (one Celery-beat tick every `settings.discovery_prewarm_interval_minutes`,
a small bounded batch per tick), so live users mostly hit an already-warm
cache instead of triggering a live scrape. Deliberately demand-driven, not a
blind rotation over every possible niche x city combo: it only ever refreshes
rows that real searches have actually created, so it never spends a scrape on
a combo nobody asked for. Requires Redis + a running worker + beat process —
see settings.discovery_prewarm_enabled.
"""
import asyncio
import logging

from sqlalchemy import select

from app.core.config import settings
from app.db.models.discovery_cache import DiscoveryCache
from app.db.session import async_session_maker
from app.services import discovery_cache_service, discovery_service
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# A stale row's own item_count is the refresh target, but never ask for fewer
# than this — a row that was thin last time still deserves a real attempt.
MIN_REFRESH_LIMIT = 10


@celery_app.task(name="prewarm_discovery_cache", bind=True, max_retries=0)
def prewarm_discovery_cache(self) -> None:
    if not settings.discovery_prewarm_enabled:
        return
    try:
        asyncio.run(_prewarm_async())
    except Exception:
        logger.exception("Discovery cache pre-warm tick failed")


async def _prewarm_async() -> None:
    async with async_session_maker() as session:
        result = await session.execute(
            select(DiscoveryCache)
            .order_by(DiscoveryCache.expires_at.asc())
            .limit(settings.discovery_prewarm_batch_size)
        )
        rows = list(result.scalars().all())

    for row in rows:
        await _refresh_one(row.niche, row.city, row.country, row.country_code, row.item_count)


async def _refresh_one(niche: str, city: str, country: str, country_code: str, item_count: int) -> None:
    limit = max(item_count, MIN_REFRESH_LIMIT)
    try:
        items = await discovery_service.discover_businesses(
            niche, city, country, country_code=country_code, limit=limit
        )
    except discovery_service.DiscoveryUnavailableError as exc:
        logger.info("Pre-warm skipped %s/%s/%s (sources unavailable): %s", niche, city, country_code, exc)
        return
    except Exception:
        logger.exception("Pre-warm failed for %s/%s/%s", niche, city, country_code)
        return

    async with async_session_maker() as session:
        await discovery_cache_service.upsert_cache(
            session, niche, city, country_code,
            niche_display=niche, city_display=city, country_display=country,
            items=items,
        )
    logger.info("Pre-warmed %s/%s/%s: %d leads", niche, city, country_code, len(items))
