import asyncio
import logging
import re
from typing import Optional

import httpx

from app.data.niches import resolve_niche_tags

logger = logging.getLogger(__name__)

# Public Overpass instances, raced concurrently (see _run_overpass_query). The
# main instance (overpass-api.de) is a free shared community resource and is
# frequently overloaded (504 "server too busy") at peak times — this is not
# specific to our usage, so we fall back across mirrors rather than treating
# the first timeout as fatal.
OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.osm.ch/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

DEFAULT_RADIUS_METERS = 15_000
# Overpass server-side query timeout, in seconds. Kept modest — the mirrors are
# raced concurrently, so total worst-case wait is ~this, not 3x this.
OVERPASS_TIMEOUT_SECONDS = 12
OVERPASS_HTTP_TIMEOUT = 15.0
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
        # can tag "name" in the local script (e.g. Urdu), and we want English
        # throughout the results.
        name = tags.get("name:en") or tags.get("name")
        if not name:
            continue
        # If there's no name:en and the raw name isn't in Latin script, we have
        # no reliable English rendering of it — drop the result rather than
        # show a name in a script the user can't read.
        if not _is_latin_script(name):
            continue

        center = el.get("center") or {"lat": el.get("lat"), "lon": el.get("lon")}
        lat, lon = center.get("lat"), center.get("lon")

        # addr:city/addr:street are frequently tagged in the local script for
        # non-Latin regions — since we already know the English city name the
        # user searched for, use that instead of trusting the raw OSM tag, and
        # drop a street line that isn't in Latin script rather than show it.
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
    """Fires all mirrors at once and returns as soon as one comes back with actual
    results, instead of trying them one at a time — a sequential fallback across
    5 mirrors could take 5x the per-mirror timeout before giving up, far too slow
    for an interactive search. A mirror that responds fast but empty (some public
    mirrors have incomplete regional data) isn't treated as final — we keep
    waiting for a fuller answer from another mirror until all have reported in."""
    last_error: Optional[BaseException] = None
    empty_result: Optional[list[dict]] = None
    async with httpx.AsyncClient(timeout=OVERPASS_HTTP_TIMEOUT, headers=OVERPASS_HEADERS) as client:
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
                        last_error = exc
                        continue
                    if result:
                        return result
                    empty_result = result
        finally:
            for task in pending:
                task.cancel()

    if empty_result is not None:
        return empty_result
    raise DiscoveryUnavailableError(
        "OpenStreetMap search is temporarily unavailable. Please try again in a moment."
    ) from last_error


async def discover_businesses(
    niche: str,
    lat: float,
    lon: float,
    city: str,
    limit: int = 50,
    radius_m: int = DEFAULT_RADIUS_METERS,
) -> list[dict]:
    tags, matched = resolve_niche_tags(niche)
    industry = niche.strip().title()

    # A 15km radius plausibly won't hold `limit` real matches for a niche
    # business type — widen once if the first pass came up short, instead of
    # silently handing back whatever the smallest radius found. Capped at two
    # tiers total: each round races 5 mirrors already, so more tiers mainly
    # adds latency (and, against rate-limited free mirrors, more 429s) rather
    # than more results — OSM's actual coverage for a niche+city is often the
    # real ceiling, not the radius.
    radii = [radius_m] if radius_m >= 50_000 else [radius_m, 50_000]
    collected: list[dict] = []
    seen_keys: set[tuple] = set()
    last_unavailable: Optional[DiscoveryUnavailableError] = None

    for r in radii:
        query = (
            _build_query(tags, lat, lon, r, limit)
            if matched
            else _build_fallback_query(niche, lat, lon, r, limit)
        )
        try:
            elements = await _run_overpass_query(query)
        except DiscoveryUnavailableError as exc:
            last_unavailable = exc
            continue

        for item in _parse_elements(elements, city, industry):
            key = (item["name"].lower(), item["phone"] or "", item["website"] or "")
            if key in seen_keys:
                continue
            seen_keys.add(key)
            collected.append(item)

        if len(collected) >= limit:
            break

    if not collected and last_unavailable:
        raise last_unavailable

    return collected[:limit]
