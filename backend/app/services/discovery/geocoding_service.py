"""Real-world lat/lon for a discovered business, via OpenStreetMap's free
Nominatim geocoder — https://nominatim.org/release-docs/latest/api/Search/

Discovery itself now also queries OpenStreetMap directly via Overpass
(overpass_service.py, one of the three parallel discovery sources alongside
Google Maps and free business directories). This module is separate: it turns
a resolved address (or, at worst, a city+country) into a real coordinate for
leads that didn't already get lat/lon from their source, instead of the
previous behavior of never geocoding at all (leads had no lat/lon, and an
unknown city silently fell back to (0, 0) — see geo_service.py).

Nominatim's usage policy (https://operations.osmfoundation.org/policies/nominatim/)
requires: max 1 request/second, and a descriptive User-Agent identifying the
app. Both are enforced here — a single process-wide lock serializes calls and
spaces them at least 1.1s apart, and results are cached in-memory per unique
query so the same city isn't re-geocoded on every lead in a batch.
"""
import asyncio
import logging
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "Crawlio-LeadDiscovery/1.0 (contact: support@crawlio.io)"
MIN_REQUEST_INTERVAL_SECONDS = 1.1

_cache: dict[str, Optional[dict]] = {}
_poi_cache: dict[str, list[dict]] = {}
_lock = asyncio.Lock()
_last_request_at = 0.0


def _cache_key(query: str) -> str:
    return " ".join(query.lower().split())


async def _throttle() -> None:
    global _last_request_at
    now = time.monotonic()
    wait = MIN_REQUEST_INTERVAL_SECONDS - (now - _last_request_at)
    if wait > 0:
        await asyncio.sleep(wait)
    _last_request_at = time.monotonic()


async def geocode(query: str) -> Optional[dict]:
    """Resolve a free-text address/city/country string to a real coordinate.
    Returns {"lat": float, "lon": float, "display_name": str} or None if
    Nominatim has nothing for this query. Never raises — geocoding failure
    should never break the rest of enrichment."""
    query = (query or "").strip()
    if not query:
        return None

    key = _cache_key(query)
    if key in _cache:
        return _cache[key]

    async with _lock:
        # Re-check inside the lock: a concurrent caller may have already
        # geocoded this exact query while we were waiting for our turn.
        if key in _cache:
            return _cache[key]

        await _throttle()
        result: Optional[dict] = None
        try:
            async with httpx.AsyncClient(timeout=15.0, headers={"User-Agent": USER_AGENT}) as client:
                resp = await client.get(
                    NOMINATIM_URL,
                    params={
                        "q": query,
                        "format": "jsonv2",
                        "limit": 1,
                        "addressdetails": 0,
                        # Without this Nominatim localizes display_name into
                        # the region's own language (e.g. Urdu for Pakistan) —
                        # every other field in a lead is English, so force it.
                        "accept-language": "en",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Nominatim geocoding failed for %r: %s", query, exc)
            data = []

        if data:
            first = data[0]
            try:
                result = {
                    "lat": float(first["lat"]),
                    "lon": float(first["lon"]),
                    "display_name": first.get("display_name") or query,
                }
            except (KeyError, TypeError, ValueError):
                result = None

        _cache[key] = result
        return result


async def geocode_business(address: Optional[str], city: str, country: str) -> Optional[dict]:
    """Best-effort geocode for a discovered business: prefer its real street
    address if one was found (from JSON-LD or AI extraction), falling back to
    city+country — city-level accuracy is still far better than no coordinate
    at all or the old (0, 0) fallback."""
    candidates = []
    if address and address.strip().lower() not in {city.strip().lower(), ""}:
        candidates.append(f"{address}, {city}, {country}".strip(", "))
    candidates.append(f"{city}, {country}".strip(", "))

    for candidate in candidates:
        result = await geocode(candidate)
        if result:
            return result
    return None


# --- Nominatim POI search (a second, distinct discovery surface over OSM) -------

_SOCIAL_TAG_KEYS = {
    "contact:facebook": "facebook",
    "facebook": "facebook",
    "contact:instagram": "instagram",
    "instagram": "instagram",
    "contact:linkedin": "linkedin",
    "linkedin": "linkedin",
    "contact:twitter": "twitter",
    "twitter": "twitter",
    "contact:whatsapp": "whatsapp",
    "whatsapp": "whatsapp",
}


def _poi_record(item: dict, city_en: str) -> Optional[dict]:
    """Turn one Nominatim search result into a lead-shaped record. Requires a
    name and real coordinates; phone/website/email/socials come from the OSM
    `extratags`, which is exactly the same data source Overpass uses — just
    reached through a free-text query instead of tag matching."""
    name = (item.get("name") or "").strip()
    if not name:
        return None
    try:
        lat = float(item.get("lat"))
        lon = float(item.get("lon"))
    except (TypeError, ValueError):
        return None

    extra = item.get("extratags") or {}
    phone = extra.get("contact:phone") or extra.get("phone")
    website = extra.get("contact:website") or extra.get("website")
    email = extra.get("contact:email") or extra.get("email")

    addr = item.get("address") or {}
    street_line = ", ".join(p for p in [addr.get("house_number"), addr.get("road")] if p)
    address = f"{street_line}, {city_en}" if street_line else city_en

    social_links: dict[str, str] = {}
    for tag_key, platform in _SOCIAL_TAG_KEYS.items():
        value = extra.get(tag_key)
        if value and platform not in social_links:
            social_links[platform] = value

    return {
        "name": name,
        "phone": phone,
        "email": email,
        "website": website,
        "address": address,
        "social_links": social_links,
        "lat": lat,
        "lon": lon,
        "source": "nominatim",
    }


async def search_places(niche: str, city: str, country: str, limit: int = 20) -> list[dict]:
    """Search OSM for business POIs by free text (``"{niche} in {city},
    {country}"``) — a discovery surface Nominatim offers natively that
    complements Overpass's tag matching, reusing the same rate-limited/cached
    client as :func:`geocode` so the two never exceed Nominatim's 1 req/s
    policy combined. Best-effort throughout: returns [] on any failure so it
    can never block the overall discovery search."""
    if limit < 1:
        return []
    query = f"{niche} in {city}, {country}".strip()
    if not query:
        return []
    limit = max(1, min(limit, 30))

    key = _cache_key(query)
    if key in _poi_cache:
        return list(_poi_cache[key])

    results: list[dict] = []
    async with _lock:
        if key in _poi_cache:
            return list(_poi_cache[key])
        await _throttle()
        try:
            async with httpx.AsyncClient(timeout=15.0, headers={"User-Agent": USER_AGENT}) as client:
                resp = await client.get(
                    NOMINATIM_URL,
                    params={
                        "q": query,
                        "format": "jsonv2",
                        "limit": limit,
                        "addressdetails": 1,
                        "extratags": 1,
                        "accept-language": "en",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Nominatim POI search failed for %r: %s", query, exc)
            data = []

        for item in data:
            record = _poi_record(item, city)
            if record:
                results.append(record)

    _poi_cache[key] = results
    return list(results)
