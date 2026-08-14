"""Lead discovery orchestrator (open-source, free sources).

Turns a niche + city/country query into a list of *real*, complete business
leads by fanning out to five independent free sources and merging their
results:

  1. Google Maps (Playwright)      — primary; real phone/address/rating/hours
  2. OSM/Overpass                  — secondary; structured POIs + real lat/lon
  3. Nominatim POI search          — OSM's own free-text POI surface, no key
  4. Geoapify Places               — keyed OSM POI search (free tier), optional
  5. Free Pakistan directories     — extra businesses, some emails

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
from typing import Optional

from app.core.config import settings
from app.core.integration_runtime import api_key
from app.services.discovery import (
    geo_service,
    geoapify_service,
    geocoding_service,
    overpass_service,
    website_lookup_service,
)
from app.services.discovery.crawlers import (

    directory_scraper,
    lead_merger,
    lead_validator,
    maps_crawler,
    web_search_service,
)
from app.services.discovery.contact_extraction import clean_business_name, is_own_website

from app.services.lead.lead_quality import data_quality


logger = logging.getLogger(__name__)

_NEARBY_CITY_FALLBACKS = 2
# Enrichment budget for the enhanced (Pro) "AI-assisted contact lookup" path:
# raw candidates missing contact info get their website looked up and scraped
# so name-only OSM/Geoapify/Nominatim records become real, contact-validated
# leads. Capped to bound request latency (each scrape is a real site visit).
_CANDIDATE_ENRICH_CAP = 40
_LOOKUP_CONCURRENCY = 6


class DiscoveryUnavailableError(Exception):
    pass


def _clean_record(item: dict, niche: str, country_code: str) -> Optional[dict]:
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
    niche: str, city: str, country: str, limit: int, use_maps: bool = True, country_code: str = "PK"
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
    tasks = [
        overpass_service.discover_businesses(niche, city, country, limit),
        directory_scraper.search_businesses(niche, city, country, limit),
        # Nominatim POI search — free, no key, reuses the shared 1 req/s
        # Nominatim throttle/cache alongside geocoding.
        geocoding_service.search_places(niche, city, country, limit),
        # Geoapify Places — free keyed OSM POI search (3k/day), skipped when
        # no key is configured. Needs the country *code* for its city anchor.
        geoapify_service.search_businesses(niche, city, country_code, limit),
    ]
    names = ["osm", "directory", "nominatim", "geoapify"]
    if use_maps:
        tasks.insert(0, maps_crawler.search_businesses(niche, city, country, limit))
        names.insert(0, "maps")

    outcomes = await asyncio.gather(*tasks, return_exceptions=True)

    source_counts: dict[str, int] = {"maps": 0, "osm": 0, "directory": 0, "nominatim": 0, "geoapify": 0}
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


async def _enrich_candidates(
    candidates: list[dict], city: str, country: str, country_code: str
) -> list[dict]:
    """Best-effort contact recovery for candidates that survived merging but
    carry no phone/email yet — the core of the enhanced ("AI-assisted contact
    lookup") discovery path.

    For each such candidate with a name: if it has a website, its own site is
    scraped for contact info (email MX-verified, phone normalized); if it has
    no website, DuckDuckGo (free, keyless) is used to find the business's own
    site first, then that is scraped. Directory/portal/social results are
    filtered out so we never attribute a listing page to a business. Candidates
    that still come up empty are simply dropped by the validator afterwards —
    nothing here fabricates data, and the whole step never raises.

    Bounded: at most `_CANDIDATE_ENRICH_CAP` candidates per call, website
    lookups throttled, one shared browser for all scrapes in the batch.
    """
    indices = [
        i for i, c in enumerate(candidates)
        if (c.get("name") or "").strip() and not (c.get("phone") or c.get("email"))
    ][:_CANDIDATE_ENRICH_CAP]
    if not indices:
        return candidates
    subset = [candidates[i] for i in indices]

    semaphore = asyncio.Semaphore(_LOOKUP_CONCURRENCY)

    async def _find(c: dict) -> Optional[str]:
        if c.get("website"):
            return c["website"]
        async with semaphore:
            return await website_lookup_service.find_business_website(c["name"], city, country)

    found = await asyncio.gather(*(_find(c) for c in subset))
    for c, website in zip(subset, found):
        if website:
            c["website"] = website

    enrich_indices = [i for i, c in zip(indices, subset) if c.get("website")]
    if not enrich_indices:
        return candidates

    # Lazy import: enrichment_pipeline imports back into this package, and at
    # module top level that would be a circular import during package init.
    from app.services.enrichment import enrichment_pipeline

    try:
        enriched = await enrichment_pipeline.enrich_items_batch(
            [candidates[i] for i in enrich_indices],
            city=city,
            country=country,
            country_code=country_code,
            use_browser=True,
            use_ai=True,
            use_google_maps=True,
        )
    except Exception as exc:  # enrichment must never break a discovery search
        logger.warning("Candidate enrichment failed for %s in %s: %s", city, country, exc)
        return candidates
    for i, result in zip(enrich_indices, enriched):
        if isinstance(result, dict) and result.get("name"):
            candidates[i] = result
    logger.info("Candidate enrichment touched %d of %d raw candidates", len(enrich_indices), len(indices))
    return candidates


async def discover_businesses(
    niche: str,
    city: str,
    country: str,
    country_code: str = "PK",
    limit: int = 50,
    enrich_candidates: bool = False,
    source_counts: Optional[dict[str, int]] = None,
) -> list[dict]:
    """Return up to `limit` real, contact-validated businesses for a niche in a
    city/country. Raises DiscoveryUnavailableError only when the requested
    city's sources are all unavailable (not merely thin on results — that's
    handled by the nearby-city/Tavily fallbacks below).

    `enrich_candidates=True` (enhanced/Pro plans) additionally runs the
    AI-assisted contact lookup on raw candidates *before* validation, so
    name-only OSM/Geoapify/Nominatim records can gain a website-scraped contact
    channel and qualify as leads. When provided, `source_counts` is filled with
    the per-source raw candidate counts (diagnostics for the API layer).
    """
    if limit < 1:
        return []

    candidates, raw_counts, engaged = await _scrape_city_sources(niche, city, country, limit, country_code=country_code)
    if source_counts is not None:
        source_counts.clear()
        source_counts.update(raw_counts)
    if not engaged:
        raise DiscoveryUnavailableError(
            "All lead sources are temporarily unavailable. Please try again in a moment."
        )

    for item in candidates:
        item.setdefault("result_city", city)
        item.setdefault("is_fallback_city", False)

    merged = lead_merger.merge_businesses(candidates)
    if enrich_candidates:
        merged = await _enrich_candidates(merged, city, country, country_code)
    cleaned = _validate_all(merged, niche, country_code, limit)

    logger.info(
        "Discovery for %s in %s: maps=%d osm=%d directory=%d nominatim=%d geoapify=%d -> merged=%d -> validated=%d",
        niche, city, raw_counts["maps"], raw_counts["osm"], raw_counts["directory"],
        raw_counts["nominatim"], raw_counts["geoapify"], len(merged), len(cleaned),
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
                niche, nearby["name"], country, remaining, use_maps=False, country_code=country_code
            )
            if not nb_engaged:
                continue
            for item in nb_candidates:
                item["result_city"] = nearby["name"]
                item["is_fallback_city"] = True
            candidates.extend(nb_candidates)
            merged = lead_merger.merge_businesses(candidates)
            if enrich_candidates:
                merged = await _enrich_candidates(merged, city, country, country_code)
            cleaned = _validate_all(merged, niche, country_code, limit)
            logger.info(
                "Nearby-city fallback %s for %s (requested %s): maps=%d osm=%d directory=%d nominatim=%d geoapify=%d -> %d total",
                nearby["name"], niche, city, nb_counts["maps"], nb_counts["osm"], nb_counts["directory"],
                nb_counts["nominatim"], nb_counts["geoapify"], len(cleaned),
            )

    # Last-resort, opt-in top-up when everything above still came up short —
    # never runs otherwise, and never overrides anything already found (see
    # web_search_service.py and lead_merger._SOURCE_PRIORITY).
    if settings.tavily_enabled and api_key("tavily_api_key") and len(cleaned) < limit:
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
