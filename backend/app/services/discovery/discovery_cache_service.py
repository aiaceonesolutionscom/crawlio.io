"""Shared, global cache of validated lead-discovery results, keyed by
niche+city+country — NOT workspace-scoped. The same search from any
workspace or company reuses a prior scrape instead of re-hitting Google
Maps/OSM/directories, which is the main lever for serving high daily volume
on free infrastructure: most of the cost of "300-500 leads/day across many
users" disappears once real-world query overlap (common niches, major
cities) turns most requests into cache hits instead of fresh live scrapes.

Every read/write is best-effort — a cache failure must never break a live
search, so both functions swallow exceptions and log instead of raising.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.data.niches import canonical_niche_key
from app.db.models.discovery_cache import DiscoveryCache

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


async def get_cached(session: AsyncSession, niche: str, city: str, country_code: str) -> Optional[tuple[list[dict[str, Any]], datetime]]:
    """Return (items, cached_at) for this niche+city+country, or None on a
    miss, an expired entry, or a cache-read failure."""
    try:
        row = await _find_row(session, canonical_niche_key(niche), _city_key(city), country_code.upper())
    except Exception as exc:
        logger.warning("Discovery cache read failed for %s/%s/%s: %s", niche, city, country_code, exc)
        return None

    if row is None or _is_expired(row):
        return None
    return list(row.items or []), row.updated_at


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
    """Insert or refresh the one cache row for this niche+city+country."""
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
    except Exception as exc:
        logger.warning("Discovery cache write failed for %s/%s/%s: %s", niche, city, country_code, exc)
        await session.rollback()
