"""Bing Maps crawler — worldwide business listings scraped from bing.com/maps.

Microsoft retired the Bing Maps Local Search REST API (Aug 2025), but the Bing
Maps *website* still serves full listings for any location on Earth, aggregating
data from Yelp, TripAdvisor and its own local-business dataset. This crawler
fetches the same search page a user would open, parses the JSON-LD and listing
markup, and returns real businesses with name/address/phone/website/rating.

TLS impersonation (curl_cffi) keeps the plain-HTTP fetch below Microsoft's bot
radar, and the per-domain rate limiter keeps us a polite visitor. Like every
crawler it never raises — blocks and markup changes degrade to [].
"""
import json
import logging
import re
from typing import Optional
from urllib.parse import quote

from app.core.config import settings
from app.services.crawlers.base import CircuitBreaker, RateLimiter, fetch_text

logger = logging.getLogger(__name__)

BASE_URL = "https://www.bing.com/maps"
TIMEOUT = 15.0

_breaker = CircuitBreaker(name="bing-maps", failure_threshold=3, cooldown_seconds=180.0)
_limiter = RateLimiter(name="bing-maps", interval=1.5)

_HEADERS = {
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.bing.com/",
}

_PHONE_RE = re.compile(r"\+?[\d\s().-]{7,16}")


def _record_from_jsonld(item: dict) -> Optional[dict]:
    """Map one JSON-LD LocalBusiness/Place node into the shared candidate shape."""
    name = item.get("name")
    if not name:
        return None
    address = item.get("address") or {}
    addr_str = address.get("streetAddress") if isinstance(address, dict) else None
    if isinstance(address, dict) and (address.get("addressLocality") or address.get("addressRegion")):
        parts = [p for p in (address.get("streetAddress"), address.get("addressLocality"), address.get("addressRegion"), address.get("postalCode"), address.get("addressCountry")) if p]
        addr_str = ", ".join(parts)
    phone = item.get("telephone") or item.get("phone")
    website = item.get("url")
    # Bing often links the business's own site here; keep only http(s) URLs.
    if website and not re.match(r"^https?://", str(website)):
        website = None
    geo = item.get("geo") or {}
    lat = geo.get("latitude") if isinstance(geo, dict) else None
    lon = geo.get("longitude") if isinstance(geo, dict) else None
    return {
        "name": str(name).strip(),
        "phone": phone,
        "website": website,
        "address": addr_str,
        "lat": lat,
        "lon": lon,
        "rating": item.get("aggregateRating", {}).get("ratingValue") if isinstance(item.get("aggregateRating"), dict) else None,
        "review_count": item.get("aggregateRating", {}).get("reviewCount") if isinstance(item.get("aggregateRating"), dict) else None,
        "source": "bing_maps",
        "social_links": {},
    }


def _extract_json_ld(html: str) -> list[dict]:
    """Pull JSON-LD script blocks that describe local businesses."""
    records: list[dict] = []
    for m in re.finditer(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', html or "", re.DOTALL | re.IGNORECASE):
        try:
            data = json.loads(m.group(1).strip())
        except (ValueError, TypeError):
            continue
        items = data.get("@graph") if isinstance(data, dict) and data.get("@graph") else data
        if isinstance(items, dict):
            items = [items]
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            typ = item.get("@type")
            types = typ if isinstance(typ, list) else [typ]
            if not any(t in {"LocalBusiness", "Place", "Restaurant", "Hotel", "MedicalBusiness", "HealthAndBeautyBusiness", "AutomotiveBusiness", "Store", "ProfessionalService"} for t in types):
                continue
            record = _record_from_jsonld(item)
            if record:
                records.append(record)
    return records


def _extract_listing_cards(html: str) -> list[dict]:
    """Fallback heuristic parse of Bing Maps listing markup when JSON-LD is
    missing. Looks for name/address/phone patterns in listing containers."""
    records: list[dict] = []
    # Bing renders results inside <li class="... listing ..."> blocks on the
    # server; grab each block's text and pick out the first strong-looking name
    # line plus any phone number.
    for block in re.findall(r'<li[^>]+class="[^"]*(?:listing|b_pSearchResult|result)[^"]*"[^>]*>(.*?)</li>', html or "", re.DOTALL | re.IGNORECASE):
        text = re.sub(r"<[^>]+>", " ", block)
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            continue
        lines = [l.strip() for l in text.split("|") if l.strip()]
        if not lines:
            continue
        name = lines[0]
        phone = None
        for line in lines:
            m = _PHONE_RE.search(line)
            if m and len(re.sub(r"\D", "", m.group())) >= 7:
                phone = m.group().strip()
                break
        record = {
            "name": name,
            "phone": phone,
            "source": "bing_maps",
            "social_links": {},
        }
        records.append(record)
    return records


async def search_businesses(niche: str, city: str, country: str, limit: int = 50) -> list[dict]:
    """Search Bing Maps for a niche in a city. Returns [] on failure/block."""
    if _breaker.open:
        logger.warning("Bing Maps circuit open — skipping crawl")
        return []
    if not settings.bing_maps_enabled:
        return []
    limit = max(1, min(limit, 100))

    # Bing Maps is worldwide: city, country so small cities resolve properly.
    where = f"{city}, {country}" if country and country.lower() not in {city.lower(), "worldwide"} else city
    url = f"{BASE_URL}?q={quote(f'{niche} {where}')}"
    await _limiter.wait()
    outcome = await fetch_text(url, headers=_HEADERS, timeout=TIMEOUT, impersonate="chrome")

    if outcome.blocked:
        logger.warning("Bing Maps returned a block/rate-limit wall for %s in %s", niche, city)
        _breaker.record_failure()
        return []
    if not outcome.ok:
        logger.info("Bing Maps returned %d for %s in %s", outcome.status, niche, city)
        return []

    records = _extract_json_ld(outcome.text)
    if len(records) < max(limit // 2, 1):
        fallback = _extract_listing_cards(outcome.text)
        seen_names = {r["name"] for r in records}
        for r in fallback:
            if r["name"] not in seen_names:
                seen_names.add(r["name"])
                records.append(r)

    for record in records:
        record.setdefault("industry", niche.strip().title())

    _breaker.record_success()
    logger.info("Bing Maps crawl for %s in %s returned %d records", niche, city, len(records))
    return records[:limit]
