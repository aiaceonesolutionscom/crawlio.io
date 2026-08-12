"""Lead discovery orchestrator (open-source, free sources).

Turns a niche + city/country query into a list of *real*, complete business
leads by fanning out to three independent free crawlers and merging their
results:

  1. Google Maps (Playwright)      — primary; real phone/address/rating/hours
  2. OSM/Overpass                  — secondary; structured POIs + real lat/lon
  3. Free Pakistan directories     — tertiary; extra businesses, some emails

Every candidate is then de-duplicated across sources (lead_merger), passed
through the real-data quality gate (lead_validator: MX-verified email, +92
normalized phone, must have a contact channel) and ranked by completeness.

When the requested city still comes up short after that (thin markets outside
the biggest cities), two further, ordered fallbacks kick in before giving up:
nearby cities in the same country (real structured data, same 3-source
pipeline, geo_service.nearby_cities) and, only after that, an opt-in Tavily
top-up (name+website only, see web_search_service.py). Real structured data
from a real place always beats a thinner stub.

Failure contract: crawlers never raise. If *every* primary source is
unavailable we raise DiscoveryUnavailableError so the API can return 503;
otherwise the search returns whatever real businesses the surviving sources
produced — never junk and never fabricated data.
"""
import asyncio
import logging

from app.core.config import settings
from app.services import geo_service, overpass_service
from app.services.crawlers import (
    directory_scraper,
    lead_merger,
    lead_validator,
    maps_crawler,
    web_search_service,
)
from app.services.contact_extraction import clean_business_name, is_own_website
from app.services.lead_quality import data_quality

logger = logging.getLogger(__name__)

_NEARBY_CITY_FALLBACKS = 2


class DiscoveryUnavailableError(Exception):
    pass


def _clean_record(item: dict, niche: str, country_code: str) -> dict | None:
    """Normalize one merged candidate into a valid lead, or drop it."""
    item = dict(item)
    if item.get("name"):
        item["name"] = clean_business_name(item["name"])
    item.setdefault("industry", niche.strip().title())
    item.setdefault("social_links", {})

    # A "website" that is actually a directory/portal listing belongs to the
    # portal, not the business — drop it so we never attribute wrong data.
    website = item.get("website")
    if website and not is_own_website(website):
        item["website"] = None

    validated = lead_validator.validate_lead(item, country_code)
    if validated is None:
        return None
    validated["completeness"] = data_quality(validated)
    return validated


def _validate_all(items: list[dict], niche: str, country_code: str, limit: int) -> list[dict]:
    cleaned: list[dict] = []
    for item in items:
        lead = _clean_record(item, niche, country_code)
        if lead is not None:
            cleaned.append(lead)
        if len(cleaned) >= limit:
            break
    return cleaned


async def _scrape_city_sources(
    niche: str, city: str, country: str, limit: int, use_maps: bool = True
) -> tuple[list[dict], dict[str, int], bool]:
    """Run the structured crawlers for one city. Returns (raw_candidates,
    per_source_counts, engaged) — engaged is True when at least one source
    actually returned something (vs. failing/empty).

    `use_maps=False` skips the Google Maps crawler — real per-place page
    visits, each with a human-pause, are by far the slowest part of a search
    (tens of seconds) and are already covered for the *requested* city.
    Nearby-city fallback trades that richness for speed: OSM + directories
    alone finish in a few seconds, so trying 1-2 nearby cities stays fast
    instead of multiplying the wait by however many cities get tried."""
    tasks = [overpass_service.discover_businesses(niche, city, country, limit),
             directory_scraper.search_businesses(niche, city, country, limit)]
    names = ["osm", "directory"]
    if use_maps:
        tasks.insert(0, maps_crawler.search_businesses(niche, city, country, limit))
        names.insert(0, "maps")

    outcomes = await asyncio.gather(*tasks, return_exceptions=True)

    source_counts: dict[str, int] = {"maps": 0, "osm": 0, "directory": 0}
    candidates: list[dict] = []
    engaged = False
    for name, outcome in zip(names, outcomes):
        if isinstance(outcome, BaseException):
            logger.warning("Discovery source %s failed for %s in %s: %s", name, niche, city, outcome)
            continue
        if not outcome:
            continue
        source_counts[name] = len(outcome)
        engaged = True
        candidates.extend(outcome)

    return candidates, source_counts, engaged


async def discover_businesses(
    niche: str,
    city: str,
    country: str,
    country_code: str = "PK",
    limit: int = 50,
) -> list[dict]:
    """Return up to `limit` real, contact-validated businesses for a niche in a
    city/country. Raises DiscoveryUnavailableError only when the requested
    city's sources are all unavailable (not merely thin on results — that's
    handled by the nearby-city/Tavily fallbacks below)."""
    if limit < 1:
        return []

    candidates, source_counts, engaged = await _scrape_city_sources(niche, city, country, limit)
    if not engaged:
        raise DiscoveryUnavailableError(
            "All lead sources are temporarily unavailable. Please try again in a moment."
        )

    for item in candidates:
        item.setdefault("result_city", city)
        item.setdefault("is_fallback_city", False)

    merged = lead_merger.merge_businesses(candidates)
    cleaned = _validate_all(merged, niche, country_code, limit)

    logger.info(
        "Discovery for %s in %s: maps=%d osm=%d directory=%d -> merged=%d -> validated=%d",
        niche, city, source_counts["maps"], source_counts["osm"], source_counts["directory"],
        len(merged), len(cleaned),
    )

    # Nearby-city fallback: only engages when the *primary* city's sources are
    # healthy but genuinely thin on results (e.g. Islamabad vs. Karachi) — real
    # structured data from a real nearby city, not a stub, tried before Tavily.
    if len(cleaned) < limit:
        for nearby in geo_service.nearby_cities(country_code, city, n=_NEARBY_CITY_FALLBACKS):
            if len(cleaned) >= limit:
                break
            remaining = limit - len(cleaned)
            nb_candidates, nb_counts, nb_engaged = await _scrape_city_sources(
                niche, nearby["name"], country, remaining, use_maps=False
            )
            if not nb_engaged:
                continue
            for item in nb_candidates:
                item["result_city"] = nearby["name"]
                item["is_fallback_city"] = True
            candidates.extend(nb_candidates)
            merged = lead_merger.merge_businesses(candidates)
            cleaned = _validate_all(merged, niche, country_code, limit)
            logger.info(
                "Nearby-city fallback %s for %s (requested %s): maps=%d osm=%d directory=%d -> %d total",
                nearby["name"], niche, city, nb_counts["maps"], nb_counts["osm"], nb_counts["directory"], len(cleaned),
            )

    # Last-resort, opt-in top-up when everything above still came up short —
    # never runs otherwise, and never overrides anything already found (see
    # web_search_service.py and lead_merger._SOURCE_PRIORITY).
    if settings.tavily_enabled and settings.tavily_api_key and len(cleaned) < limit:
        extra = await web_search_service.find_extra_businesses(niche, city, country, limit - len(cleaned))
        if extra:
            remerged = lead_merger.merge_businesses(cleaned + extra)
            cleaned = _validate_all(remerged, niche, country_code, limit)
            logger.info(
                "Tavily top-up for %s in %s: +%d candidates -> %d total",
                niche, city, len(extra), len(cleaned),
            )

    # Most complete first so the requested cap is filled with the best leads.
    cleaned.sort(key=lambda r: data_quality(r), reverse=True)
    return cleaned[:limit]
