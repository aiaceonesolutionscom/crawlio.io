import logging
from typing import Optional

from app.data.cities import CITIES
from app.data.countries import COUNTRIES

logger = logging.getLogger(__name__)


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


def search_cities(country_code: str, query: str, limit: int = 8) -> list[dict]:
    """City autocomplete from a static major-city list — no geocoding service.
    Coordinates are approximate (kept only for the API shape; discovery is
    web-based and ignores them). If the country or city isn't in the list, the
    typed query is passed through as a free-text city so any location still
    works for a web search."""
    q = (query or "").strip()
    if len(q) < 2:
        return []

    city_list = CITIES.get(country_code.upper(), [])
    matches = [c for c in city_list if c["name"].lower().startswith(q.lower())]
    if not matches:
        matches = [c for c in city_list if q.lower() in c["name"].lower()]
    if matches:
        return matches[:limit]
    return [{"name": q, "lat": 0.0, "lon": 0.0}]