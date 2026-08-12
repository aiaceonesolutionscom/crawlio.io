import logging
import math
from typing import Optional

from app.data.cities import CITIES
from app.data.countries import COUNTRIES

logger = logging.getLogger(__name__)


def _is_real_coord(city: dict) -> bool:
    # search_cities() passes through an unmatched free-text query as a
    # {"name": q, "lat": 0.0, "lon": 0.0} placeholder — (0, 0) is "Null
    # Island", never a real business location, so it must never be treated
    # as a real coordinate for distance math.
    return not (city.get("lat") == 0.0 and city.get("lon") == 0.0)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


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


def nearby_cities(country_code: str, city_name: str, n: int = 2) -> list[dict]:
    """The N nearest other major cities in the same country, by straight-line
    distance — a discovery fallback for when the requested city's own results
    are thin (e.g. Islamabad -> Rawalpindi). Pure offline haversine math over
    the static CITIES list, no geocoding call. Returns [] when the origin
    city isn't in the static list (so its coordinates aren't known), or the
    country has no other known cities (many countries only have a handful of
    entries)."""
    city_list = CITIES.get(country_code.upper(), [])
    origin = next((c for c in city_list if c["name"].lower() == city_name.strip().lower()), None)
    if origin is None or not _is_real_coord(origin):
        return []

    candidates = [
        c for c in city_list
        if c["name"].lower() != origin["name"].lower() and _is_real_coord(c)
    ]
    candidates.sort(key=lambda c: _haversine_km(origin["lat"], origin["lon"], c["lat"], c["lon"]))
    return candidates[:n]