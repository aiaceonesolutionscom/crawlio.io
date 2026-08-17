"""BizData crawler — free worldwide business data via the OSM-powered BizData API.

BizData (https://bizdata-web.vercel.app) is a free REST API built on OpenStreetMap
data: no API key, no signup, no billing, worldwide coverage. It returns names,
addresses, phones, websites, emails and coordinates for 37 business categories.

Because it wraps the same OSM data the Overpass crawler already uses, it slots in
as a *fast* structured supplement: one clean JSON call instead of Overpass's
query+retry dance, especially valuable in Europe/Asia where OSM coverage is
dense. Like every other crawler it never raises — failures degrade to [].
"""
import json
import logging
import re
from typing import Optional

from app.core.config import settings
from app.services.crawlers.base import CircuitBreaker, fetch_text

logger = logging.getLogger(__name__)

# BizData's category list uses machine-friendly slugs that rarely match a user's
# free-text niche. We pass the niche through verbatim first (the API matches
# fuzzy), then fall back to known category slugs for common niches.
BASE_URL = "https://bizdata-web.vercel.app"
TIMEOUT = 20.0

_breaker = CircuitBreaker(name="bizdata", failure_threshold=3, cooldown_seconds=120.0)

# Niche keywords -> BizData category slug. Order matters: first match wins.
_CATEGORY_MAP = {
    "dentist": "dentist",
    "dental": "dentist",
    "doctor": "doctor",
    "hospital": "hospital",
    "clinic": "clinic",
    "pharmac": "pharmacy",
    "restaurant": "restaurant",
    "cafe": "cafe",
    "coffee": "cafe",
    "hotel": "hotel",
    "gym": "gym",
    "beauty": "beauty salon",
    "salon": "beauty salon",
    "plumber": "plumber",
    "electrician": "electrician",
    "lawyer": "lawyer",
    "attorney": "lawyer",
    "accountant": "accountant",
    "real estate": "real estate agency",
    "agency": "real estate agency",
    "school": "school",
    "college": "school",
    "university": "school",
    "supermarket": "supermarket",
    "grocery": "supermarket",
    "bakery": "bakery",
    "bank": "bank",
    "store": "store",
    "shop": "store",
}


def _category_for(niche: str) -> Optional[str]:
    lowered = (niche or "").lower()
    for keyword, slug in _CATEGORY_MAP.items():
        if keyword in lowered:
            return slug
    return None


def _parse_businesses(payload: dict) -> list[dict]:
    """Map a BizData /api/businesses response into the shared candidate shape."""
    records: list[dict] = []
    for biz in (payload.get("businesses") or []):
        if not isinstance(biz, dict) or not biz.get("name"):
            continue
        record = {
            "name": biz.get("name"),
            "phone": biz.get("phone"),
            "email": biz.get("email"),
            "website": biz.get("website"),
            "address": biz.get("address"),
            "lat": biz.get("lat") or biz.get("latitude"),
            "lon": biz.get("lon") or biz.get("longitude"),
            "category": biz.get("category"),
            "source": "bizdata",
            "social_links": {},
        }
        records.append(record)
    return records


async def search_businesses(niche: str, city: str, country: str, limit: int = 50) -> list[dict]:
    """Query BizData for a niche in a city. Returns [] on any failure (never
    raises) so the orchestrator can fall back to other sources."""
    if _breaker.open:
        logger.warning("BizData circuit open — skipping crawl")
        return []
    if not settings.bizdata_enabled:
        return []
    limit = max(1, min(limit, 100))

    queries: list[dict] = [{"location": city}]
    category = _category_for(niche)
    if category:
        queries.append({"location": city, "category": category})
        # Country-qualified location improves resolution for small cities.
        queries.append({"location": f"{city}, {country}", "category": category})

    records: list[dict] = []
    seen: set[str] = set()
    for params in queries:
        if len(records) >= limit:
            break
        query = "&".join(f"{k}={v.replace(' ', '%20')}" for k, v in params.items())
        url = f"{BASE_URL}/api/businesses?{query}&limit={limit}"
        try:
            outcome = await fetch_text(url, timeout=TIMEOUT, impersonate="chrome")
        except Exception as exc:
            logger.warning("BizData fetch failed for %s in %s: %s", niche, city, exc)
            _breaker.record_failure()
            continue
        if outcome.blocked:
            logger.warning("BizData returned a block/rate-limit wall for %s in %s", niche, city)
            _breaker.record_failure()
            continue
        if not outcome.ok:
            logger.info("BizData returned %d for %s in %s", outcome.status, niche, city)
            continue
        try:
            import json

            payload = json.loads(outcome.text)
        except (ValueError, TypeError) as exc:
            logger.warning("BizData returned non-JSON for %s in %s: %s", niche, city, exc)
            _breaker.record_failure()
            continue
        for record in _parse_businesses(payload):
            key = (record.get("name") or "").lower() + "|" + re.sub(r"\D", "", record.get("phone") or "")
            if key in seen:
                continue
            seen.add(key)
            records.append(record)
        _breaker.record_success()

    # Tag with the niche so downstream validation/merging has consistent context.
    for record in records:
        record.setdefault("industry", niche.strip().title())
    return records[:limit]
