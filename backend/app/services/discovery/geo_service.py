import logging
import math
from typing import Optional

from app.data.cities import CITIES
from app.data.countries import COUNTRIES

logger = logging.getLogger(__name__)


def _is_real_coord(city: dict) -> bool:
    # (0, 0) is "Null Island", never a real business location — guards any
    # static CITIES entry missing real coordinates from distance math.
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


async def search_cities(country_code: str, query: str, limit: int = 8) -> list[dict]:
    """City autocomplete for one country. Checks the static major-city list
    first (instant, no network); when that has nothing — most of the 187
    supported countries aren't in it at all, and even listed ones only carry
    a handful of biggest cities — falls back to a live Nominatim lookup
    scoped to that exact country (geocoding_service.search_cities_in_country).

    Never echoes the raw query back as if it were a validated city: doing
    that previously let any typed text pass as a "city" for any country (e.g.
    typing "New Delhi" while Country=Pakistan showed it as a Pakistani city
    suggestion). No match anywhere now means no suggestion, not a fake one.

    An empty query returns the country's known major cities unfiltered, so
    picking a country alone (before typing anything) already surfaces real
    cities to choose from."""
    q = (query or "").strip()
    city_list = CITIES.get(country_code.upper(), [])

    if not q:
        return city_list[:limit]
    if len(q) < 2:
        return []

    matches = [c for c in city_list if c["name"].lower().startswith(q.lower())]
    if not matches:
        matches = [c for c in city_list if q.lower() in c["name"].lower()]
    if matches:
        return matches[:limit]

    from app.services.discovery import geocoding_service
    return await geocoding_service.search_cities_in_country(country_code, q, limit)


def city_center(country_code: str, city_name: str) -> Optional[dict]:
    """Approximate center coordinates for a known city (from the static
    CITIES list), or None when the city isn't listed (so its coordinates
    aren't known). Used by sources that need a geo anchor (Geoapify's
    circle filter) rather than a free-text city search."""
    city_list = CITIES.get(country_code.upper(), [])
    for c in city_list:
        if c["name"].lower() == (city_name or "").strip().lower() and _is_real_coord(c):
            return c
    return None


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


def top_cities(country_code: str, n: int = 2) -> list[dict]:
    """The country's first (largest) cities from the static CITIES list, used
    as a last-resort country-wide discovery fallback when the requested city
    and its neighbors are all thin. Pure offline — no geocoding call."""
    city_list = CITIES.get(country_code.upper(), [])
    if not city_list:
        return []
    return city_list[:n]