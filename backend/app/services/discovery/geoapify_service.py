"""Geoapify Places — a free, keyed Places API over OpenStreetMap data.

Free tier is 3,000 requests/day with no billing card required. Data is the
same OSM POI dataset as Overpass/Nominatim but reached through Geoapify's own
search surface, which often surfaces businesses a tag-only Overpass query
misses, and every result carries structured fields (name, formatted address,
coordinates) plus the raw OSM tags under ``properties.datasource.raw`` — the
source of phone/website/email/social links.

The live API has no free-text `text` search: it requires a `categories` (and a
location `filter`). So we map the requested niche onto a Geoapify category and
query a `circle` centered on the city's static CITIES coordinates — both offline
and free. Unmapped niches return [] (skipped), never a junk guess.

Additive discovery source with the project's standard failure contract: skipped
entirely when no API key is configured, returns [] on any error, never raises,
so it can never block or fail the overall discovery search.
"""
import logging
from typing import Optional

import httpx

from app.core.config import settings
from app.core.integration_runtime import api_key
from app.services.discovery.geo_service import city_center

logger = logging.getLogger(__name__)

GEOAPIFY_URL = "https://api.geoapify.com/v2/places"
TIMEOUT = 15.0
DEFAULT_LIMIT = 20
# Radius (meters) of the circle filter around the city center. Covers the
# urban core of a major city without spilling into neighboring towns.
CIRCLE_RADIUS_M = 20_000

# Niche keywords -> Geoapify category. First keyword hit wins; categories are
# kept to ones the live API accepts (verified against api.geoapify.com).
_NICHE_CATEGORY_MAP = (
    ("dentist", "healthcare.dentist"),
    ("dental", "healthcare.dentist"),
    ("clinic", "healthcare"),
    ("doctor", "healthcare"),
    ("medical", "healthcare"),
    ("hospital", "healthcare"),
    ("health", "healthcare"),
    ("restaurant", "catering.restaurant"),
    ("cafe", "catering.cafe"),
    ("coffee", "catering.cafe"),
    ("food", "catering"),
    ("supermarket", "commercial.supermarket"),
    ("grocery", "commercial.supermarket"),
    ("shop", "commercial"),
    ("store", "commercial"),
    ("gym", "sport.fitness"),
    ("fitness", "sport.fitness"),
    ("hotel", "accommodation.hotel"),
    ("lodging", "accommodation.hotel"),
    ("school", "education"),
    ("university", "education"),
    ("college", "education"),
    ("bank", "service"),
    ("salon", "service"),
    ("beauty", "service"),
    ("spa", "service"),
)


def _category_for_niche(niche: str) -> Optional[str]:
    """Map a free-text niche onto a Geoapify category, or None when there is
    no safe mapping (the source then returns [] for that search)."""
    text = (niche or "").strip().lower()
    if not text:
        return None
    for keyword, category in _NICHE_CATEGORY_MAP:
        if keyword in text:
            return category
    return None

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


def _parse_feature(feature: dict, city_en: str) -> Optional[dict]:
    """Turn one Geoapify Places feature into a lead-shaped record. Keeps
    everything the response actually knows (name, address, phone, website,
    email, social links, hours, coordinates) — no field is invented."""
    props = feature.get("properties") or {}
    raw = props.get("datasource", {}).get("raw") or {}
    name = (props.get("name") or raw.get("name") or "").strip()
    if not name:
        return None

    coords = feature.get("geometry", {}).get("coordinates") or []
    lat = props.get("lat")
    lon = props.get("lon")
    if len(coords) >= 2:
        if lat is None:
            lat = coords[1]
        if lon is None:
            lon = coords[0]
    try:
        if lat is not None:
            lat = float(lat)
        if lon is not None:
            lon = float(lon)
    except (TypeError, ValueError):
        lat, lon = None, None

    # Geoapify publishes phones under several raw keys — most commonly `mobile`
    # for cell numbers, plus `phone`/`contact:phone` and `fax` for landlines —
    # so check them all (and any props-level phone/mobile) before giving up.
    phone = (
        raw.get("contact:phone")
        or raw.get("phone")
        or raw.get("mobile")
        or raw.get("contact:mobile")
        or raw.get("fax")
        or props.get("phone")
        or props.get("mobile")
    )
    website = raw.get("contact:website") or raw.get("website") or props.get("website")
    email = raw.get("contact:email") or raw.get("email")

    line1 = props.get("address_line1") or ""
    line2 = props.get("address_line2") or ""
    address = line1 if line1 == line2 else ", ".join(p for p in [line1, line2] if p)
    if not address:
        # address_line* are sometimes just the business name; fall back to the
        # raw street/city tags, which carry the real street address.
        street = ", ".join(p for p in [raw.get("housenumber"), raw.get("street")] if p)
        raw_city = raw.get("city") or raw.get("addr:city")
        address = ", ".join(p for p in [street, raw_city or city_en] if p)
    if not address:
        address = city_en

    social_links: dict[str, str] = {}
    for tag_key, platform in _SOCIAL_TAG_KEYS.items():
        value = raw.get(tag_key) or props.get(tag_key)
        if value and platform not in social_links:
            social_links[platform] = str(value).strip()

    hours = None
    opening = props.get("opening_hours")
    if isinstance(opening, dict):
        text = opening.get("weekday_text")
        if isinstance(text, list) and text:
            hours = "; ".join(str(t).strip() for t in text if str(t).strip())
    elif isinstance(opening, str) and opening.strip():
        hours = opening.strip()

    record = {
        "name": name,
        "phone": phone,
        "email": email,
        "website": website,
        "address": address,
        "social_links": social_links,
        "lat": lat,
        "lon": lon,
        "source": "geoapify",
    }
    if hours:
        record["hours"] = hours
    return record


async def search_businesses(niche: str, city: str, country_code: str, limit: int = 50) -> list[dict]:
    """Geoapify Places category search for a niche around a city. Returns []
    on any failure, when no API key is configured, or when the niche can't be
    mapped to a supported category — never raises."""
    key = api_key("geoapify_api_key")
    if not settings.geoapify_enabled or not key or limit < 1:
        return []
    category = _category_for_niche(niche)
    center = city_center(country_code, city)
    if not category or not center:
        logger.info(
            "Geoapify skipped for %s in %s (category=%s, center=%s)",
            niche, city, category, bool(center),
        )
        return []
    limit = max(1, min(limit, 50))

    params = {
        "categories": category,
        "filter": f"circle:{center['lon']},{center['lat']},{CIRCLE_RADIUS_M}",
        "bias": f"proximity:{center['lon']},{center['lat']}",
        "limit": limit,
        "apiKey": key,
        "lang": "en",
    }
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(GEOAPIFY_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Geoapify search failed for %s in %s: %s", niche, city, exc)
        return []

    records: list[dict] = []
    seen: set[tuple] = set()
    for feature in data.get("features") or []:
        record = _parse_feature(feature, city)
        if not record:
            continue
        dedup_key = (record["name"].lower(), record["phone"] or "", record["website"] or "")
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        record.setdefault("industry", niche.strip().title())
        records.append(record)
        if len(records) >= limit:
            break

    return records
