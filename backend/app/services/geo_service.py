import logging
from typing import Optional

import httpx

from app.data.countries import COUNTRIES

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# Nominatim's usage policy requires a descriptive User-Agent and no more than ~1 req/s;
# we're a single backend proxying user-triggered autocomplete, not bulk scraping.
NOMINATIM_HEADERS = {"User-Agent": "crawlio-lead-discovery/1.0 (contact: support@crawlio.io)"}


def search_countries(query: Optional[str], limit: int = 20) -> list[dict[str, str]]:
    if not query:
        return COUNTRIES[:limit]
    q = query.strip().lower()
    matches = [c for c in COUNTRIES if c["name"].lower().startswith(q)]
    if len(matches) < limit:
        matches += [
            c for c in COUNTRIES
            if q in c["name"].lower() and c not in matches
        ]
    return matches[:limit]


def country_name_for_code(code: str) -> Optional[str]:
    for c in COUNTRIES:
        if c["code"] == code.upper():
            return c["name"]
    return None


async def search_cities(country_code: str, query: str, limit: int = 8) -> list[dict]:
    country_name = country_name_for_code(country_code)
    if not country_name or not query or len(query.strip()) < 2:
        return []

    params = {
        "city": query.strip(),
        "country": country_name,
        "format": "jsonv2",
        "addressdetails": "1",
        "limit": str(limit),
        # Without this, Nominatim returns names in the local script (e.g. "کراچی"
        # for Karachi) based on the region rather than English.
        "accept-language": "en",
    }
    try:
        async with httpx.AsyncClient(timeout=8.0, headers=NOMINATIM_HEADERS) as client:
            resp = await client.get(NOMINATIM_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError):
        logger.warning("Nominatim city search failed for %s/%s", country_code, query)
        return []

    results = []
    seen_names = set()
    for item in data:
        address = item.get("address", {})
        name = address.get("city") or address.get("town") or address.get("village") or item.get("name")
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        try:
            lat, lon = float(item["lat"]), float(item["lon"])
        except (KeyError, ValueError):
            continue
        results.append({"name": name, "lat": lat, "lon": lon})
    return results
