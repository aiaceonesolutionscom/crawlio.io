"""OpenStreetMap Overpass — a structured, free POI database that returns real
per-venue lat/lon, street address, and often phone/website/social tags
directly, unlike a generic web search. Runs strictly ADDITIVE and
non-blocking alongside discovery_service.py's other sources (Google Maps,
business directories): on any failure (all mirrors down, geocoding failure,
bad query) this module returns an empty list, never raises. It was dropped
once before for exactly the opposite behavior — being a required, blocking
source against a free shared resource that overloads at peak times — so the
failure contract here is the actual fix, not the query/mirror logic, which
was already reasonable.
"""
import asyncio
import logging
import re
from typing import Optional

import httpx

from app.data.niches import resolve_niche_tags
from app.services.discovery import geocoding_service

logger = logging.getLogger(__name__)

# Public Overpass instances, raced concurrently (see _run_overpass_query).
# overpass-api.de is a free shared community resource and is frequently
# overloaded (504 "server too busy") at peak times — this isn't specific to
# our usage, so we fall back across mirrors rather than treating one timeout
# as fatal. Racing more mirrors concurrently only improves odds and costs no
# extra serial time, since FIRST_COMPLETED returns as soon as any responds.
OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.osm.ch/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

DEFAULT_RADIUS_METERS = 15_000
# Overpass server-side query timeout, in seconds. Kept modest — the mirrors
# are raced concurrently, so total worst-case wait is ~this, not 5x this.
OVERPASS_TIMEOUT_SECONDS = 12
OVERPASS_HTTP_TIMEOUT = 15.0
# The public Overpass instances 406 any User-Agent that doesn't look like
# curl's own default (confirmed empirically). Overpass has no documented UA
# requirement unlike Nominatim, so this just mirrors whatever their edge/WAF
# allowlists.
OVERPASS_HEADERS = {"User-Agent": "curl/8.4.0"}


def _build_query(tags: list[dict[str, str]], lat: float, lon: float, radius_m: int, limit: int) -> str:
    around = f"around:{radius_m},{lat},{lon}"
    if not tags:
        return ""
    clauses = []
    for tag in tags:
        (key, value), = tag.items()
        clauses.append(f'node["{key}"="{value}"]({around});')
        clauses.append(f'way["{key}"="{value}"]({around});')
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


_LATIN_RE = re.compile(r"^[\x00-\x7FÀ-ɏ\s,.\-/#&'()]*$")


def _is_latin_script(text: Optional[str]) -> bool:
    return bool(text) and bool(_LATIN_RE.match(text))


_SOCIAL_TAG_KEYS = {
    "contact:facebook": "facebook",
    "facebook": "facebook",
    "contact:instagram": "instagram",
    "instagram": "instagram",
    "contact:linkedin": "linkedin",
    "linkedin": "linkedin",
    "contact:twitter": "twitter",
    "twitter": "twitter",
}


def _social_links_from_tags(tags: dict) -> dict[str, str]:
    links: dict[str, str] = {}
    for tag_key, platform in _SOCIAL_TAG_KEYS.items():
        value = tags.get(tag_key)
        if value and platform not in links:
            links[platform] = value
    return links


def _parse_elements(elements: list[dict], city_en: str, industry: str) -> list[dict]:
    results = []
    seen = set()
    for el in elements:
        tags = el.get("tags", {})
        # Prefer the English name tag when a mapper set one — OSM contributors
        # can tag "name" in the local script (e.g. Urdu), and results must
        # stay in English throughout.
        name = tags.get("name:en") or tags.get("name")
        if not name:
            continue
        # If there's no name:en and the raw name isn't Latin script, there's
        # no reliable English rendering — drop it rather than show a name in
        # a script the user can't read.
        if not _is_latin_script(name):
            continue

        center = el.get("center") or {"lat": el.get("lat"), "lon": el.get("lon")}
        lat, lon = center.get("lat"), center.get("lon")

        # addr:city/addr:street are frequently tagged in the local script for
        # non-Latin regions — since we already know the English city name the
        # user searched for, use that instead of trusting the raw OSM tag,
        # and drop a street line that isn't Latin script rather than show it.
        street_line = ", ".join(p for p in [tags.get("addr:housenumber"), tags.get("addr:street")] if p)
        if street_line and not _is_latin_script(street_line):
            street_line = ""
        address = f"{street_line}, {city_en}" if street_line else city_en

        website = tags.get("website") or tags.get("contact:website")
        phone = tags.get("phone") or tags.get("contact:phone")
        email = tags.get("email") or tags.get("contact:email")

        # A result with nothing but a name isn't an actionable lead.
        if not (phone or email or website or street_line):
            continue

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
            "industry": industry,
            "social_links": _social_links_from_tags(tags),
            "lat": lat,
            "lon": lon,
            "source": "openstreetmap",
        })
    return results


async def _query_one_mirror(client: httpx.AsyncClient, mirror: str, query: str) -> list[dict]:
    resp = await client.post(mirror, data={"data": query})
    resp.raise_for_status()
    return resp.json().get("elements", [])


async def _run_overpass_query(query: str) -> list[dict]:
    """Fires all mirrors at once and returns as soon as one comes back with
    actual results, instead of trying them one at a time — a sequential
    fallback across 5 mirrors could take 5x the per-mirror timeout before
    giving up, far too slow for an interactive search. Retried once after a
    short pause when every mirror fails or returns nothing, because the public
    mirrors are flaky under load (504/429) and a single instant can collapse
    an entire search to directory-only results. Never raises: on total mirror
    failure, logs and returns an empty list so this source can never block or
    fail the overall discovery search."""
    empty_result: Optional[list[dict]] = None
    async with httpx.AsyncClient(timeout=OVERPASS_HTTP_TIMEOUT, headers=OVERPASS_HEADERS) as client:
        for attempt in range(2):
            tasks = {
                asyncio.create_task(_query_one_mirror(client, mirror, query)): mirror
                for mirror in OVERPASS_MIRRORS
            }
            pending = set(tasks)
            try:
                while pending:
                    done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                    for task in done:
                        try:
                            result = task.result()
                        except (httpx.HTTPError, ValueError) as exc:
                            logger.warning("Overpass mirror %s failed: %s", tasks[task], exc)
                            continue
                        if result:
                            return result
                        empty_result = result
            finally:
                for task in pending:
                    task.cancel()
            if attempt == 0:
                await asyncio.sleep(1.0)

    return empty_result if empty_result is not None else []


async def discover_businesses(niche: str, city: str, country: str, limit: int = 50, wider_radius: bool = False) -> list[dict]:
    """Additive OSM/Overpass discovery source. Geocodes city+country to a
    center point (reusing geocoding_service's rate-limited/cached Nominatim
    client), then queries Overpass around that point. Best-effort throughout:
    returns [] rather than raising on any failure (geocode miss, all mirrors
    down, empty result) so it never blocks the overall discovery search.

    When ``wider_radius=True`` the search uses progressively larger search
    radii (100km → 250km) to catch businesses further out — used by the
    discovery-service retry pass when a primary-city scrape came up short."""
    if limit < 1:
        return []

    center = await geocoding_service.geocode(f"{city}, {country}")
    if not center:
        logger.info("Overpass discovery skipped for %s, %s: geocoding failed", city, country)
        return []

    tags, matched = resolve_niche_tags(niche)
    industry = niche.strip().title()

    # Standard radii: 15km -> 50km for a normal search. When wider_radius is
    # requested (retry pass), push out to 100km -> 250km to catch businesses
    # on the outskirts that the default tiers miss.
    radii = [100_000, 250_000, 400_000] if wider_radius else [DEFAULT_RADIUS_METERS, 50_000]
    collected: list[dict] = []
    seen_keys: set[tuple] = set()

    for radius_m in radii:
        query = (
            _build_query(tags, center["lat"], center["lon"], radius_m, limit)
            if matched
            else _build_fallback_query(niche, center["lat"], center["lon"], radius_m, limit)
        )
        elements = await _run_overpass_query(query)

        for item in _parse_elements(elements, city, industry):
            key = (item["name"].lower(), item["phone"] or "", item["website"] or "")
            if key in seen_keys:
                continue
            seen_keys.add(key)
            collected.append(item)

        if len(collected) >= limit:
            break

    return collected[:limit]
