"""Shared, global cache of validated lead-discovery results, keyed by
niche+city+country — NOT workspace-scoped. The same search from any
workspace or company reuses a prior scrape instead of re-hitting Google
Maps/OSM/directories, which is the main lever for serving high daily volume
on free infrastructure: most of the cost of "300-500 leads/day across many
users" disappears once real-world query overlap (common niches, major
cities) turns most requests into cache hits instead of fresh live scrapes.

Every read/write is best-effort — a cache failure must never break a live
search, so both functions swallow exceptions and log instead of raising.

INTEGRATED SAFETY LAYER: CacheQualityValidator
This module now validates cached entries against quality thresholds before
returning them. Stale/partial caches (e.g. "1 result" entries) are rejected
to prevent yesterday's "50 search → 1 result" regression.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.data.niches import canonical_niche_key
from app.db.models.discovery_cache import DiscoveryCache
from app.services.discovery.discovery_safety import (
    CacheQualityValidator,
    cache_validator,
    compute_query_hash,
    should_bypass_cache,
)

logger = logging.getLogger(__name__)


def _city_key(city: str) -> str:
    return (city or "").strip().lower()


def _is_expired(row: DiscoveryCache) -> bool:
    if row.expires_at is None:
        return False
    expires_at = row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at < datetime.now(timezone.utc)


async def _find_row(session: AsyncSession, niche_key: str, city_key: str, country_code: str) -> Optional[DiscoveryCache]:
    result = await session.execute(
        select(DiscoveryCache).where(
            DiscoveryCache.niche_key == niche_key,
            DiscoveryCache.city_key == city_key,
            DiscoveryCache.country_code == country_code,
        )
    )
    return result.scalar_one_or_none()


async def get_cached(
    session: AsyncSession,
    niche: str,
    city: str,
    country_code: str,
    requested_limit: int = 50,
) -> Optional[tuple[list[dict[str, Any]], datetime]]:
    """Return (items, cached_at) for this niche+city+country, or None on a
    miss, an expired entry, a quality failure, or a cache-read error.

    Integrated with CacheQualityValidator: entries that don't meet quality
    thresholds (e.g. < 5 items, low completeness score) are treated as misses
    to prevent stale/partial data from being served to users.
    """
    try:
        row = await _find_row(
            session, canonical_niche_key(niche), _city_key(city), country_code.upper()
        )
    except Exception as exc:
        logger.warning("Discovery cache read failed for %s/%s/%s: %s", niche, city, country_code, exc)
        return None

    if row is None or _is_expired(row):
        return None

    items = list(row.items or [])

    # SAFETY CHECK 1: Bypass cache if it's severely under-delivering
    if should_bypass_cache(len(items), requested_limit):
        logger.info(
            "Cache bypass: %s/%s/%s has only %d items (requested %d). "
            "Triggering fresh discovery.",
            niche, city, country_code, len(items), requested_limit,
        )
        return None

    # SAFETY CHECK 2: Validate cache quality before serving
    query_hash = compute_query_hash(niche, city, country_code)
    is_valid, reason = cache_validator.is_cache_valid(
        cached_items=items,
        query_hash=query_hash,
        requested_limit=requested_limit,
        generated_at=row.updated_at,
    )

    if not is_valid:
        logger.info(
            "Cache quality reject: %s/%s/%s - %s (%d items)",
            niche, city, country_code, reason, len(items),
        )
        return None

    logger.debug(
        "Cache hit: %s/%s/%s - %d items validated",
        niche, city, country_code, len(items),
    )
    return items, row.updated_at


async def upsert_cache(
    session: AsyncSession,
    niche: str,
    city: str,
    country_code: str,
    niche_display: str,
    city_display: str,
    country_display: str,
    items: list[dict[str, Any]],
    source_counts: Optional[dict[str, Any]] = None,
) -> None:
    """Insert or refresh the one cache row for this niche+city+country.

    Also records quality metrics for the cache entry so future reads can
    validate whether the cached data is still reliable.
    """
    niche_key = canonical_niche_key(niche)
    city_key = _city_key(city)
    cc = country_code.upper()
    try:
        row = await _find_row(session, niche_key, city_key, cc)
        if row is None:
            row = DiscoveryCache(niche_key=niche_key, city_key=city_key, country_code=cc)
            session.add(row)

        row.niche = niche_display
        row.city = city_display
        row.country = country_display
        row.items = items
        row.item_count = len(items)
        row.source_counts = source_counts
        row.expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.discovery_cache_ttl_hours)

        await session.commit()

        # Record cache quality metrics for future validation
        query_hash = compute_query_hash(niche, city, country_code)
        cache_validator.record_cache_quality(
            query_hash=query_hash,
            items=items,
            source_counts=source_counts or {},
            total_time=0.0,  # Will be set by caller in future enhancement
        )

    except Exception as exc:
        logger.warning("Discovery cache write failed for %s/%s/%s: %s", niche, city, country_code, exc)
        await session.rollback()
