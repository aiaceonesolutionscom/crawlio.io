import logging
import re
from typing import Optional

import httpx

from app.data.niches import resolve_niche_tags

logger = logging.getLogger(__name__)

# Public Overpass instances, tried in order. The main instance (overpass-api.de) is
# a free shared community resource and is frequently overloaded (504 "server too
# busy") at peak times — this is not specific to our usage, so we fall back across
# mirrors rather than treating the first timeout as fatal.
OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

DEFAULT_RADIUS_METERS = 15_000
OVERPASS_TIMEOUT_SECONDS = 20
# The public Overpass instances 406 any User-Agent that doesn't look like curl's
# own default (confirmed empirically: httpx's default UA, a descriptive custom
# UA, and a browser UA were all rejected; "curl/x.y.z" was accepted). Unlike
# Nominatim, Overpass has no documented UA requirement, so this just mirrors
# whatever their edge/WAF allowlists.
OVERPASS_HEADERS = {"User-Agent": "curl/8.4.0"}


class DiscoveryUnavailableError(Exception):
    pass


def _build_query(tags: list[dict[str, str]], lat: float, lon: float, radius_m: int, limit: int) -> str:
    around = f"around:{radius_m},{lat},{lon}"
    if tags:
        clauses = []
        for tag in tags:
            (key, value), = tag.items()
            clauses.append(f'node["{key}"="{value}"]({around});')
            clauses.append(f'way["{key}"="{value}"]({around});')
    else:
        return ""
    body = "\n  ".join(clauses)
    return f"[out:json][timeout:{OVERPASS_TIMEOUT_SECONDS}];\n(\n  {body}\n);\nout center {limit};"


def _build_fallback_query(keyword: str, lat: float, lon: float, radius_m: int, limit: int) -> str:
    """No direct tag mapping for this niche — search by name across common
    commercial tag categories instead. Less precise, but better than nothing."""
    around = f"around:{radius_m},{lat},{lon}"
    escaped = re.sub(r'[".\\]', "", keyword)
    clauses = []
    for key in ("shop", "office", "amenity", "craft", "healthcare", "leisure", "tourism"):
        clauses.append(f'node["{key}"]["name"~"{escaped}",i]({around});')
        clauses.append(f'way["{key}"]["name"~"{escaped}",i]({around});')
    body = "\n  ".join(clauses)
    return f"[out:json][timeout:{OVERPASS_TIMEOUT_SECONDS}];\n(\n  {body}\n);\nout center {limit};"


def _parse_elements(elements: list[dict]) -> list[dict]:
    results = []
    seen = set()
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name")
        if not name:
            continue

        center = el.get("center") or {"lat": el.get("lat"), "lon": el.get("lon")}
        lat, lon = center.get("lat"), center.get("lon")

        address_parts = [
            tags.get("addr:housenumber"),
            tags.get("addr:street"),
            tags.get("addr:city") or tags.get("addr:suburb"),
        ]
        address = ", ".join(p for p in address_parts if p) or None

        website = tags.get("website") or tags.get("contact:website")
        phone = tags.get("phone") or tags.get("contact:phone")
        email = tags.get("email") or tags.get("contact:email")

        dedup_key = (name.lower(), phone or "", website or "")
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        results.append({
            "name": name,
            "phone": phone,
            "email": email,
            "website": website,
            "address": address,
            "lat": lat,
            "lon": lon,
            "source": "openstreetmap",
        })
    return results


async def _run_overpass_query(query: str) -> list[dict]:
    last_error: Optional[Exception] = None
    async with httpx.AsyncClient(timeout=OVERPASS_TIMEOUT_SECONDS + 5, headers=OVERPASS_HEADERS) as client:
        for mirror in OVERPASS_MIRRORS:
            try:
                resp = await client.post(mirror, data={"data": query})
                resp.raise_for_status()
                data = resp.json()
                return data.get("elements", [])
            except (httpx.HTTPError, ValueError) as exc:
                logger.warning("Overpass mirror %s failed: %s", mirror, exc)
                last_error = exc
                continue
    raise DiscoveryUnavailableError(
        "OpenStreetMap search is temporarily unavailable. Please try again in a moment."
    ) from last_error


async def discover_businesses(
    niche: str, lat: float, lon: float, limit: int = 50, radius_m: int = DEFAULT_RADIUS_METERS
) -> list[dict]:
    tags, matched = resolve_niche_tags(niche)
    if matched:
        query = _build_query(tags, lat, lon, radius_m, limit)
    else:
        query = _build_fallback_query(niche, lat, lon, radius_m, limit)

    elements = await _run_overpass_query(query)
    return _parse_elements(elements)[:limit]
