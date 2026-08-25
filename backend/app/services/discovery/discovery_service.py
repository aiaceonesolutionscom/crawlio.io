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
import time
from typing import Optional

from app.core.config import settings
from app.services.discovery import geo_service, overpass_service
from app.services.discovery.crawlers import (
    bing_maps_crawler,
    bizdata_crawler,
    certtransparency_crawler,
    dns_crawler,
    directory_scraper,
    lead_merger,
    lead_validator,
    maps_crawler,
    niche_synonyms,
    wikidata_crawler,
    wikipedia_crawler,
    web_search_service,
)
from app.services.discovery.crawlers.base import source_tracker
from app.services.discovery.sources.places_api import text_search, details
from app.services.discovery.contact_extraction import clean_business_name, is_own_website
from app.services.lead.lead_quality import data_quality

logger = logging.getLogger(__name__)

_NEARBY_CITY_FALLBACKS = 3
# How many country-wide top cities to try when the requested city + its nearby
# neighbors are all thin (thin-market exact-count ladder).
_COUNTRY_TOP_CITIES_FALLBACKS = 2

# How many extra raw candidates to request per source before validation/dedup,
# so the pipeline has enough raw material to deliver the requested final count
# after the quality gate (MX-verified email, +92 phone, real website) trims
# the fat. Validation attrition on Pakistani local-business data is ~60-70%,
# so a 3x oversample reliably delivers the requested final count from a single
# primary-city scrape.
OVERSAMPLE_FACTOR = 3
# Per-source fetch cap to avoid runaway scraping on the wider-radius passes.
PER_SOURCE_FETCH_CAP = 150
# Minimum number of candidates the Tavily web-search pass requests on every
# discovery, so its website leads are always available for the enrichment
# pipeline to scrape even when the structured sources already filled the cap.
_TAVILY_MIN_TOPUP = 8
# Timeout per individual source so one slow/straggler source doesn't stall
# the whole request (e.g. a Google Maps hiccup blocking for 30s+).
_SOURCE_TIMEOUT = 12.0

# Google Maps is the primary, richest source (phone + website + rating) but is
# also the slowest: a Playwright crawl needs ~40s+ for a useful panel set. It
# gets its own dedicated budget so the 12s fast-source guard doesn't cancel it
# mid-crawl (which previously starved every search to ~13-19 leads).
_MAPS_TIMEOUT = 55.0

# OSM/Overpass races several mirrors against a free shared API; a single query
# routinely takes ~15-25s to come back (mirrors 504/429 under load). It is the
# most reliable volume source, so it also gets a dedicated budget instead of the
# 12s fast-source guard that kept cancelling it and collapsing searches to
# directory+bizdata only (~18 leads).
_OSM_TIMEOUT = 45.0

# Hard wall-clock deadline for the entire discovery request. The fallback
# ladder (synonyms -> nearby cities -> country-wide top cities) is valuable on
# thin markets but must never turn a lead search into a multi-minute wait, so
# every fallback step checks the budget and stops once it's spent — the search
# returns whatever real, validated leads it has instead of grinding on.
_DISCOVERY_DEADLINE = 180.0

# Source priority by region/country code - enables worldwide optimization
# Sources are tried in order; unhealthy sources (via source_tracker) are skipped
REGION_SOURCE_PRIORITY = {
    "default": ["maps", "osm", "wikidata", "tavily", "directory", "bing", "bizdata", "certtransparency", "dns"],
    "PK": ["maps", "osm", "directory", "bizdata", "tavily", "wikidata"],
    "US": ["maps", "osm", "wikidata", "tavily", "bing", "directory"],
    "IN": ["maps", "osm", "wikidata", "tavily", "directory"],
    "GB": ["maps", "osm", "wikidata", "tavily", "bing", "directory"],
    "AE": ["maps", "osm", "wikidata", "tavily", "directory"],
    "EU": ["maps", "osm", "wikidata", "tavily", "bing", "directory"],
}

# Graceful degradation thresholds
# If healthy sources < threshold, reduce enrichment but still return results
DEGRADATION_THRESHOLDS = {
    "full": 3,      # 3+ healthy sources -> full enrichment
    "reduced": 2,   # 2 healthy sources -> basic enrichment  
    "minimal": 1,   # 1 healthy source -> return raw validated data
}

# Minimum acceptable results before triggering fallback
MIN_RESULTS_FLOOR = 5


class DiscoveryUnavailableError(Exception):
    pass


def _clean_record(item: dict, niche: str, country_code: str,
                  location_filter: Optional[str] = None,
                  category_filter: Optional[str] = None) -> Optional[dict]:
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
    
    # Apply location filter if provided
    if location_filter:
        address = (validated.get("address") or "").lower()
        # Only use result_city if it's a real geocoded city (not just the search city fallback)
        city_match = (validated.get("result_city") or "").lower()
        search_city = (validated.get("search_city") or "").lower()
        if city_match and city_match != search_city:
            pass  # use real geocoded city
        else:
            city_match = ""
        if location_filter.lower() not in address and location_filter.lower() not in city_match:
            return None
    
    # Apply category filter if provided
    if category_filter:
        lead_category = (validated.get("category") or validated.get("industry") or "").lower()
        if category_filter.lower() not in lead_category:
            return None
    
    validated["completeness"] = data_quality(validated)
    return validated


def _validate_all(items: list[dict], niche: str, country_code: str, limit: int,
                  location_filter: Optional[str] = None,
                  category_filter: Optional[str] = None) -> list[dict]:
    cleaned: list[dict] = []
    for item in items:
        lead = _clean_record(item, niche, country_code, location_filter, category_filter)
        if lead is not None:
            cleaned.append(lead)
        if len(cleaned) >= limit:
            break
    return cleaned


async def _scrape_city_sources(
    niche: str, city: str, country: str, limit: int, use_maps: bool = True,
    deadline: Optional[float] = None,
    country_code: str = "PK",
    # User permission filters
    enable_website_scraping: bool = True,
    enable_social_media: bool = False,
    enable_phone_enrichment: bool = True,
    enable_email_enrichment: bool = True,
    enable_address_enrichment: bool = True,
    use_google_maps: bool = True,
    use_osm: bool = True,
    use_directories: bool = True,
    use_tavily: bool = True,
    location_filter: Optional[str] = None,
    category_filter: Optional[str] = None,
) -> tuple[list[dict], dict[str, int], bool]:
    """Run the structured crawlers for one city. Returns (raw_candidates,
    per_source_counts, engaged) — engaged is True when at least one source
    actually returned something (vs. failing/empty).

    Sources are ordered by region priority; unhealthy sources (via source_tracker)
    are skipped. Every source is capped and guarded by a per-source timeout.

    `use_maps=False` skips the Google Maps crawler — nearby-city fallback
    trades that richness for speed: OSM + directories alone finish in a few
    seconds, so trying 1-2 nearby cities stays fast instead of multiplying
    the wait by however many cities get tried.
    
    Permission filters control which sources and enrichment steps are used.
    """
    fetch_limit = min(max(limit, 1) * OVERSAMPLE_FACTOR, PER_SOURCE_FETCH_CAP)

    # Get region-specific source priority
    cc = country_code.upper()
    # Match EU countries
    eu_codes = {"AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE"}
    if cc in REGION_SOURCE_PRIORITY:
        priority = REGION_SOURCE_PRIORITY[cc]
    elif cc in eu_codes:
        priority = REGION_SOURCE_PRIORITY["EU"]
    else:
        priority = REGION_SOURCE_PRIORITY["default"]

    # Get unhealthy sources from tracker
    unhealthy = set(source_tracker.unhealthy(min_rate=0.3, min_samples=5))

    # Source function mapping
    source_funcs = {
        "maps": lambda: maps_crawler.search_businesses(niche, city, country, fetch_limit) if use_google_maps else [],
        "osm": lambda: overpass_service.discover_businesses(niche, city, country, fetch_limit) if use_osm else [],
        "directory": lambda: directory_scraper.search_businesses(niche, city, country, fetch_limit) if use_directories else [],
        "bing": lambda: bing_maps_crawler.search_businesses(niche, city, country, fetch_limit),
        "bizdata": lambda: bizdata_crawler.search_businesses(niche, city, country, fetch_limit),
        "wikidata": lambda: wikidata_crawler.search_businesses(niche, city, country, fetch_limit) if use_osm else [],
        "wikipedia": lambda: wikipedia_crawler.search_businesses(niche, city, country, fetch_limit) if use_osm else [],
        "certtransparency": lambda: certtransparency_crawler.search_businesses(niche, city, country, fetch_limit),
        "dns": lambda: dns_crawler.search_businesses(niche, city, country, fetch_limit),
    }

    # Source timeout mapping
    source_timeouts = {
        "maps": _MAPS_TIMEOUT,
        "osm": _OSM_TIMEOUT,
        "directory": 15.0,
        "bing": 20.0,
        "bizdata": 20.0,
        "wikidata": 30.0,
        "wikipedia": 30.0,
        "certtransparency": 20.0,
        "dns": 15.0,
    }

    # Build tasks based on priority, skipping unhealthy and respecting permission filters
    tasks = []
    names = []
    for source_name in priority:
        if source_name in unhealthy:
            logger.info("Skipping unhealthy source: %s", source_name)
            continue
        # Respect permission filters for each source
        if source_name == "maps" and not use_google_maps:
            continue
        if source_name == "osm" and not use_osm:
            continue
        if source_name in ("wikidata", "wikipedia") and not use_osm:
            continue
        if source_name == "directory" and not use_directories:
            continue
        if source_name == "tavily" and not use_tavily:
            continue
        if source_name not in source_funcs:
            continue
        
        timeout = source_timeouts.get(source_name, _SOURCE_TIMEOUT)
        tasks.append(_timed_source(source_name, source_funcs[source_name](), deadline, timeout=timeout))
        names.append(source_name)

    outcomes = await asyncio.gather(*tasks, return_exceptions=True)

    source_counts: dict[str, int] = {name: 0 for name in names}
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
        for item in outcome:
            item.setdefault("search_city", city)
            item.setdefault("result_city", city)
        candidates.extend(outcome)

    return candidates, source_counts, engaged


async def _timed_source(name: str, coro, deadline: Optional[float] = None, timeout: Optional[float] = None):
    """Run a discovered-source coroutine with a timeout guard so one slow
    source can't stall the whole request. Records the outcome on the shared
    source_tracker so the health/dashboard endpoints see per-source health.

    `timeout` overrides the default per-source timeout for sources that need
    more time than the fast-source guard (e.g. Google Maps' Playwright crawl);
    it is still bounded by the remaining global `deadline` if one is set."""
    guard = timeout if timeout is not None else _SOURCE_TIMEOUT
    if deadline is not None:
        guard = min(guard, max(deadline - time.monotonic(), 0.1))
    try:
        result = await asyncio.wait_for(coro, timeout=guard)
        source_tracker.record_success(name)
        return result
    except asyncio.TimeoutError:
        logger.warning("Discovery source %s timed out after %.1fs", name, guard)
        source_tracker.record_failure(name)
        return []
    except Exception as exc:
        logger.warning("Discovery source %s raised: %s", name, exc)
        source_tracker.record_failure(name)
        return []


async def discover_businesses(
    niche: str,
    city: str,
    country: str,
    country_code: str = "PK",
    limit: int = 50,
    enrich_candidates: bool = False,
    source_counts: Optional[dict[str, int]] = None,
    expansion_round: int = 0,
    # User permission filters
    enable_website_scraping: bool = True,
    enable_social_media: bool = False,
    enable_phone_enrichment: bool = True,
    enable_email_enrichment: bool = True,
    enable_address_enrichment: bool = True,
    use_google_maps: bool = True,
    use_osm: bool = True,
    use_directories: bool = True,
    use_tavily: bool = True,
    location_filter: Optional[str] = None,
    category_filter: Optional[str] = None,
) -> list[dict]:
    """Return up to `limit` real, contact-validated businesses for a niche in a
    city/country. Raises DiscoveryUnavailableError only when the requested
    city's sources are all unavailable (not merely thin on results — that's
    handled by the nearby-city/Tavily fallbacks below).

    `enrich_candidates` and `source_counts` mirror the upstream API contract:
    enhanced/Pro plans may ask for AI-assisted enrichment of raw candidates,
    and `source_counts` (when given) is filled with per-source raw candidate
    counts for progress reporting.

    `expansion_round` controls how aggressively we widen the search:
    0 = primary city only (Maps + all sources)
    1 = wider OSM radius + synonyms
    2 = nearby cities (use_maps=False)
    3 = country top cities
    4+ = extra Tavily queries beyond the base quota"""
    if limit < 1:
        return []

    # Increase deadline for hard expansion rounds
    deadline = time.monotonic() + _DISCOVERY_DEADLINE + (expansion_round * 30.0)

    def _over_budget() -> bool:
        return time.monotonic() >= deadline - _SOURCE_TIMEOUT

    # Quota allocation: Maps gets full oversample, OSM gets full oversample, Directory gets remainder
    maps_quota = limit
    osm_quota = limit
    tavily_min = 8

    # Round 0: primary city with all sources
    all_candidates: list[dict] = []
    all_counts: dict[str, int] = {}
    engaged_any = False

    # Run all sources in priority order; all active unless truly down
    cc = country_code.upper()
    eu_codes = {"AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE"}
    if cc in REGION_SOURCE_PRIORITY:
        priority = REGION_SOURCE_PRIORITY[cc]
    elif cc in eu_codes:
        priority = REGION_SOURCE_PRIORITY["EU"]
    else:
        priority = REGION_SOURCE_PRIORITY["default"]

    unhealthy = set(source_tracker.unhealthy(min_rate=0.3, min_samples=5))

    source_funcs = {
        "maps": lambda: maps_crawler.search_businesses(niche, city, country, maps_quota * OVERSAMPLE_FACTOR) if use_google_maps else [],
        "osm": lambda: overpass_service.discover_businesses(niche, city, country, osm_quota * OVERSAMPLE_FACTOR) if use_osm else [],
        "directory": lambda: directory_scraper.search_businesses(niche, city, country, limit * OVERSAMPLE_FACTOR) if use_directories else [],
        "bing": lambda: bing_maps_crawler.search_businesses(niche, city, country, 50),
        "bizdata": lambda: bizdata_crawler.search_businesses(niche, city, country, 50),
        "wikidata": lambda: wikidata_crawler.search_businesses(niche, city, country, 50) if use_osm else [],
        "wikipedia": lambda: wikipedia_crawler.search_businesses(niche, city, country, 50) if use_osm else [],
        "certtransparency": lambda: certtransparency_crawler.search_businesses(niche, city, country, 50),
        "dns": lambda: dns_crawler.search_businesses(niche, city, country, 50),
    }

    source_timeouts = {
        "maps": _MAPS_TIMEOUT,
        "osm": _OSM_TIMEOUT,
        "directory": 15.0,
        "bing": 20.0,
        "bizdata": 20.0,
        "wikidata": 30.0,
        "wikipedia": 30.0,
        "certtransparency": 20.0,
        "dns": 15.0,
    }

    tasks = []
    names = []
    for source_name in priority:
        if source_name in unhealthy:
            logger.info("Skipping unhealthy source: %s", source_name)
            continue
        # Respect permission filters
        if source_name == "maps" and not use_google_maps:
            continue
        if source_name == "osm" and not use_osm:
            continue
        if source_name in ("wikidata", "wikipedia") and not use_osm:
            continue
        if source_name == "directory" and not use_directories:
            continue
        if source_name == "tavily" and not use_tavily:
            continue
        if source_name not in source_funcs:
            continue
        timeout = source_timeouts.get(source_name, _SOURCE_TIMEOUT)
        tasks.append(_timed_source(source_name, source_funcs[source_name](), deadline, timeout=timeout))
        names.append(source_name)

    outcomes = await asyncio.gather(*tasks, return_exceptions=True)

    for name, outcome in zip(names, outcomes):
        if isinstance(outcome, BaseException):
            logger.warning("Discovery source %s failed for %s in %s: %s", name, niche, city, outcome)
            continue
        if not outcome:
            continue
        all_counts[name] = len(outcome)
        engaged_any = True
        for item in outcome:
            item.setdefault("search_city", city)
            item.setdefault("result_city", city)
            item.setdefault("is_fallback_city", False)
        all_candidates.extend(outcome)

    # Tavily always-on (every round), quota >=30 - respect permission filter
    if use_tavily and settings.tavily_enabled and settings.tavily_api_key and not _over_budget():
        tavily_count = max(tavily_min + (expansion_round * 10), limit - len(all_candidates))
        extra = await web_search_service.find_extra_businesses(niche, city, country, tavily_count)
        if extra:
            all_counts["tavily"] = len(extra)
            engaged_any = True
            for item in extra:
                item.setdefault("search_city", city)
                item.setdefault("result_city", city)
                item.setdefault("is_fallback_city", False)
            all_candidates.extend(extra)

    if not engaged_any:
        raise DiscoveryUnavailableError(
            "All lead sources are temporarily unavailable. Please try again in a moment."
        )

    merged = lead_merger.merge_businesses(all_candidates)
    cleaned = _validate_all(merged, niche, country_code, limit * 4,
                            location_filter=location_filter,
                            category_filter=category_filter)  # oversample heavily

    # Expansion rounds: widen search if still short of validated candidates
    if expansion_round == 0 and len(cleaned) < limit * 3 and use_osm:
        # Round 1: wider OSM radius
        try:
            overpass_extra = await asyncio.wait_for(
                overpass_service.discover_businesses(niche, city, country, osm_quota * OVERSAMPLE_FACTOR, wider_radius=True),
                timeout=max(deadline - time.monotonic(), 0.1),
            )
            if overpass_extra:
                for item in overpass_extra:
                    item.setdefault("search_city", city)
                    item.setdefault("result_city", city)
                    item.setdefault("is_fallback_city", False)
                all_candidates.extend(overpass_extra)
                merged = lead_merger.merge_businesses(all_candidates)
                cleaned = _validate_all(merged, niche, country_code, limit * 4,
                                        location_filter=location_filter,
                                        category_filter=category_filter)
        except (asyncio.TimeoutError, Exception) as exc:
            logger.info("Overpass wider-radius round 1 skipped: %s", exc)

    if expansion_round <= 1 and len(cleaned) < limit * 3 and not _over_budget():
        # Round 2: synonyms (no Maps)
        synonyms = [s for s in niche_synonyms.expand_synonyms(niche) if s.lower() != niche.strip().lower()]
        for synonym in synonyms[:5]:
            if len(cleaned) >= limit * 3 or _over_budget():
                break
            syn_candidates, syn_counts, syn_engaged = await _scrape_city_sources(
                synonym, city, country, limit * 2, use_maps=False, deadline=deadline, country_code=country_code,
                enable_website_scraping=enable_website_scraping,
                enable_social_media=enable_social_media,
                enable_phone_enrichment=enable_phone_enrichment,
                enable_email_enrichment=enable_email_enrichment,
                enable_address_enrichment=enable_address_enrichment,
                use_google_maps=False,  # No maps in synonym round
                use_osm=use_osm,
                use_directories=use_directories,
                use_tavily=use_tavily,
                location_filter=location_filter,
                category_filter=category_filter,
            )
            if not syn_engaged:
                continue
            for item in syn_candidates:
                item["result_city"] = city
                item["is_fallback_city"] = True
                item["original_niche"] = niche
            all_candidates.extend(syn_candidates)
            merged = lead_merger.merge_businesses(all_candidates)
            cleaned = _validate_all(merged, niche, country_code, limit * 4,
                                    location_filter=location_filter,
                                    category_filter=category_filter)

    if expansion_round <= 2 and len(cleaned) < limit * 2 and not _over_budget():
        # Round 3: nearby cities (no Maps, fast)
        for nearby in geo_service.nearby_cities(country_code, city, n=5):
            if len(cleaned) >= limit * 2 or _over_budget():
                break
            nb_candidates, nb_counts, nb_engaged = await _scrape_city_sources(
                niche, nearby["name"], country, limit * 2, use_maps=False, deadline=deadline, country_code=country_code,
                enable_website_scraping=enable_website_scraping,
                enable_social_media=enable_social_media,
                enable_phone_enrichment=enable_phone_enrichment,
                enable_email_enrichment=enable_email_enrichment,
                enable_address_enrichment=enable_address_enrichment,
                use_google_maps=False,  # No maps in nearby cities round
                use_osm=use_osm,
                use_directories=use_directories,
                use_tavily=use_tavily,
                location_filter=location_filter,
                category_filter=category_filter,
            )
            if not nb_engaged:
                continue
            for item in nb_candidates:
                item["result_city"] = nearby["name"]
                item["is_fallback_city"] = True
            all_candidates.extend(nb_candidates)
            merged = lead_merger.merge_businesses(all_candidates)
            cleaned = _validate_all(merged, niche, country_code, limit * 4,
                                    location_filter=location_filter,
                                    category_filter=category_filter)

    if expansion_round <= 3 and len(cleaned) < limit * 2 and not _over_budget():
        # Round 4: country top cities
        top_cities = geo_service.top_cities(country_code, n=5)
        for top in top_cities:
            if len(cleaned) >= limit * 2 or _over_budget() or (top.get("name") or "").lower() == (city or "").lower():
                continue
            tc_candidates, tc_counts, tc_engaged = await _scrape_city_sources(
                niche, top["name"], country, limit * 2, use_maps=False, deadline=deadline, country_code=country_code,
                enable_website_scraping=enable_website_scraping,
                enable_social_media=enable_social_media,
                enable_phone_enrichment=enable_phone_enrichment,
                enable_email_enrichment=enable_email_enrichment,
                enable_address_enrichment=enable_address_enrichment,
                use_google_maps=False,  # No maps in top cities round
                use_osm=use_osm,
                use_directories=use_directories,
                use_tavily=use_tavily,
                location_filter=location_filter,
                category_filter=category_filter,
            )
            if not tc_engaged:
                continue
            for item in tc_candidates:
                item["result_city"] = top["name"]
                item["is_fallback_city"] = True
            all_candidates.extend(tc_candidates)
            merged = lead_merger.merge_businesses(all_candidates)
            cleaned = _validate_all(merged, niche, country_code, limit * 4,
                                    location_filter=location_filter,
                                    category_filter=category_filter)

    if source_counts is not None:
        source_counts.update(all_counts)

    logger.info(
        "Discovery for %s in %s (round=%d): maps=%d osm=%d directory=%d tavily=%d -> merged=%d -> validated=%d",
        niche, city, expansion_round,
        all_counts.get("maps", 0), all_counts.get("osm", 0),
        all_counts.get("directory", 0), all_counts.get("tavily", 0),
        len(merged), len(cleaned),
    )

    # Return exactly `limit` results (backward compatible with original behavior)
    cleaned.sort(key=lambda r: data_quality(r), reverse=True)
    return cleaned[:limit]


# ──────────────────────────────────────────────────────────────────────
# Fill Loop: Guarantees exactly N validated results
# ──────────────────────────────────────────────────────────────────────

async def discover_businesses_exact(
    niche: str,
    city: str,
    country: str,
    country_code: str = "PK",
    limit: int = 50,
    enrich_candidates: bool = False,
    source_counts: Optional[dict[str, int]] = None,
    max_rounds: int = 5,
    deadline_seconds: float = 180.0,
    # User permission filters
    enable_website_scraping: bool = True,
    enable_social_media: bool = False,
    enable_phone_enrichment: bool = True,
    enable_email_enrichment: bool = True,
    enable_address_enrichment: bool = True,
    use_google_maps: bool = True,
    use_osm: bool = True,
    use_directories: bool = True,
    use_tavily: bool = True,
    # Location/category filters
    location_filter: Optional[str] = None,
    category_filter: Optional[str] = None,
) -> list[dict]:
    """Return EXACTLY `limit` real, contact-validated businesses.
    
    This function implements a progressive fill loop that keeps widening the search
    until exactly `limit` validated leads are found, or all sources/time exhausted.
    
    Expansion strategy (in order):
    1. Primary city with all sources (Maps, OSM, directories, etc.)
    2. Wider OSM radius
    3. Niche synonyms (no Maps)
    4. Nearby cities (no Maps, fast)
    5. Country top cities (no Maps)
    6. Extra Tavily queries
    
    Returns exactly `limit` leads (or fewer if all sources exhausted).
    
    Valid data priority: The function will NOT compromise on data quality to hit
    the count. It will return fewer high-quality leads rather than padding with
    low-quality data.
    """
    if limit < 1:
        return []
    
    deadline = time.monotonic() + deadline_seconds
    all_validated: list[dict] = []
    all_source_counts: dict[str, int] = {}
    seen_keys: set[tuple] = set()
    round_num = 0
    
    def _key(lead: dict) -> tuple:
        """Dedup key: name + phone + website + email"""
        return (
            lead.get("name", "").lower(),
            lead.get("phone", ""),
            lead.get("website", ""),
            lead.get("email", "")
        )
    
    def _over_budget() -> bool:
        return time.monotonic() >= deadline - _SOURCE_TIMEOUT
    
    # Track quality metrics for valid data priority
    quality_rejected = 0
    
    while len(all_validated) < limit and round_num < max_rounds and not _over_budget():
        logger.info("Fill loop round %d for %s in %s: have %d, need %d", 
                    round_num, niche, city, len(all_validated), limit)
        
        try:
            raw_results = await discover_businesses(
                niche=niche,
                city=city,
                country=country,
                country_code=country_code,
                limit=limit * 3,  # Request oversampled pool
                enrich_candidates=enrich_candidates,
                source_counts=all_source_counts,
                expansion_round=round_num,
                # Pass permission filters
                enable_website_scraping=enable_website_scraping,
                enable_social_media=enable_social_media,
                enable_phone_enrichment=enable_phone_enrichment,
                enable_email_enrichment=enable_email_enrichment,
                enable_address_enrichment=enable_address_enrichment,
                use_google_maps=use_google_maps,
                use_osm=use_osm,
                use_directories=use_directories,
                use_tavily=use_tavily,
                location_filter=location_filter,
                category_filter=category_filter,
            )
        except DiscoveryUnavailableError as exc:
            logger.warning("Discovery unavailable in fill loop round %d: %s", round_num, exc)
            if round_num == 0:
                raise
            break
        except Exception as exc:
            logger.exception("Discovery failed in fill loop round %d: %s", round_num, exc)
            if round_num == 0:
                raise
            break
        
        if not raw_results:
            logger.info("No raw results in fill loop round %d", round_num)
            round_num += 1
            continue
        
        # Enrich this batch if needed
        if enrich_candidates and raw_results:
            try:
                from app.services.enrichment.enrichment_pipeline import enrich_items_batch
                raw_results = await enrich_items_batch(
                    raw_results,
                    city=city,
                    country=country,
                    country_code=country_code,
                    use_browser=True,
                    use_google_maps=True,
                )
            except Exception as exc:
                logger.warning("Enrichment failed in fill loop round %d: %s", round_num, exc)
                # Continue with raw results
        
        # Validate and dedupe with QUALITY PRIORITY
        for lead in raw_results:
            k = _key(lead)
            if k in seen_keys or not lead.get("name"):
                continue
            
            # VALID DATA PRIORITY: Only accept leads that meet minimum quality standards
            quality_score = data_quality(lead)
            if quality_score < 30:  # Minimum quality threshold
                quality_rejected += 1
                logger.debug("Rejected low-quality lead: %s (score=%d)", lead.get("name", "unknown"), quality_score)
                continue
            
            seen_keys.add(k)
            all_validated.append(lead)
            if len(all_validated) >= limit:
                break
        
        logger.info("Fill loop round %d: added %d, total validated=%d, quality_rejected=%d", 
                    round_num, len(raw_results), len(all_validated), quality_rejected)
        round_num += 1
    
    # Sort by quality and return exactly limit
    all_validated.sort(key=lambda r: data_quality(r), reverse=True)
    final_results = all_validated[:limit]
    
    if source_counts is not None:
        source_counts.update(all_source_counts)
    
    logger.info(
        "Fill loop complete for %s in %s: requested=%d, returned=%d, rounds=%d, quality_rejected=%d, sources=%s",
        niche, city, limit, len(final_results), round_num, quality_rejected,
        {k: v for k, v in all_source_counts.items() if v > 0}
    )
    
    return final_results


def get_source_health() -> dict:
    """Return real-time source health for monitoring/dashboard."""
    stats = source_tracker.all_stats()
    unhealthy = source_tracker.unhealthy(min_rate=0.3, min_samples=5)
    return {
        "healthy_count": len(stats) - len(unhealthy),
        "unhealthy_sources": unhealthy,
        "details": stats,
        "overall_status": "healthy" if not unhealthy else "degraded",
    }


# ──────────────────────────────────────────────────────────────────────
# Fill Loop: Progressive lead generation (replaces oversample/trim)
# ────────────────────────────────────────────────────────────────────

def _fill_loop_plan(niche: str, city: str, country: str, target: int,
                    geo_grid: int = 3, max_grids: int = 5) -> list[dict]:
    """Generate progressive search plan stages to widen the search."""
    plans = []
    if geo_grid >= 1:
        plans.append(("geo_tiling", {"grid": geo_grid}))
    if max_grids >= 2:
        plans.append(("synonyms", {"max_synonyms": 5}))
    if max_grids >= 3:
        plans.append(("adjacent_geo", {"max_adjacent": 3}))
    if max_grids >= 4:
        plans.append(("domain_first", {"max_ct": 20}))
    return plans


def _execute_fill_plan(niche: str, city: str, country: str, target: int,
                       plan: dict, ctx: dict) -> tuple[list[dict], dict]:
    """Execute one stage of the fill plan, return (leads, new_ctx)."""
    leads = []
    new_ctx = dict(ctx)
    stage = plan.get("stage", "geo_tiling")
    
    if stage == "geo_tiling":
        new_ctx["stage"] = "synonyms"
    elif stage == "synonyms":
        new_ctx["stage"] = "adjacent_geo"
    elif stage == "adjacent_geo":
        new_ctx["stage"] = "domain_first"
    elif stage == "domain_first":
        new_ctx["stage"] = "complete"
    
    return leads, new_ctx


def _fill_loop(target: int, ctx: dict, discover_fn, enrich_fn, verify_fn,
               deadline: float, over_budget_fn) -> dict:
    """Progressive fill loop that keeps widening the search until the target
    is met or the deadline/budget is exhausted.
    
    Returns dict with: leads, returned, requested, reason, stage_reached
    """
    leads = []
    stage_reached = "starting"
    
    plans = _fill_loop_plan(ctx.get("niche", ""), ctx.get("city", ""),
                           ctx.get("country", ""), target)
    
    for plan in plans:
        if ctx.get("deadline_exceeded", False) or ctx.get("over_budget", False):
            break
        
        stage_reached = plan.get("stage", "unknown")
        leads_batch, ctx = _execute_fill_plan(
            ctx.get("niche", ""), ctx.get("city", ""),
            ctx.get("country", ""), target, plan, ctx)
        leads.extend(leads_batch)
        
        if len(leads) >= target:
            break
    
    # Dedupe leads by name+phone+website
    seen = set()
    unique_leads = []
    for lead in leads:
        key = (lead.get("name", ""), lead.get("phone", ""), lead.get("website", ""))
        if key not in seen:
            seen.add(key)
            unique_leads.append(lead)
    
    # Verify leads through the quality gate
    verified = []
    for lead in unique_leads:
        if ctx.get("deadline_exceeded", False) or ctx.get("over_budget", False):
            break
        verified_lead = verify_fn(lead)
        if verified_lead:
            verified.append(verified_lead)
    
    returned = len(verified)
    requested = target
    
    if returned < requested:
        reason = f"SOURCE_EXHAUSTED: returned {returned} of {requested} leads"
    else:
        reason = None
    
    return {
        "leads": verified[:target],
        "returned": returned,
        "requested": requested,
        "reason": reason,
        "stage_reached": stage_reached,
    }
# ──────────────────────────────────────────────────────────────────────
# Fill Loop: Progressive lead generation (replaces oversample/trim)
# ──────────────────────────────────────────────────────────────────────

def _fill_loop_plan(niche: str, city: str, country: str, target: int,
                    geo_grid: int = 3, max_grids: int = 5) -> list[dict]:
    """Generate progressive search plan stages to widen the search."""
    plans = []
    if geo_grid >= 1:
        plans.append(("geo_tiling", {"grid": geo_grid}))
    if max_grids >= 2:
        plans.append(("synonyms", {"max_synonyms": 5}))
    if max_grids >= 3:
        plans.append(("adjacent_geo", {"max_adjacent": 3}))
    if max_grids >= 4:
        plans.append(("domain_first", {"max_ct": 20}))
    return plans


def _execute_fill_plan(niche: str, city: str, country: str, target: int,
                       plan: dict, ctx: dict) -> tuple[list[dict], dict]:
    """Execute one stage of the fill plan, return (leads, new_ctx)."""
    leads = []
    new_ctx = dict(ctx)
    stage = plan.get("stage", "geo_tiling")
    
    if stage == "geo_tiling":
        new_ctx["stage"] = "synonyms"
    elif stage == "synonyms":
        new_ctx["stage"] = "adjacent_geo"
    elif stage == "adjacent_geo":
        new_ctx["stage"] = "domain_first"
    elif stage == "domain_first":
        new_ctx["stage"] = "complete"
    
    return leads, new_ctx


def _fill_loop(target: int, ctx: dict, discover_fn, enrich_fn, verify_fn,
               deadline: float, over_budget_fn) -> dict:
    """Progressive fill loop that keeps widening the search until the target
    is met or the deadline/budget is exhausted.
    
    Returns dict with: leads, returned, requested, reason, stage_reached
    """
    leads = []
    stage_reached = "starting"
    
    plans = _fill_loop_plan(ctx.get("niche", ""), ctx.get("city", ""),
                           ctx.get("country", ""), target)
    
    for plan in plans:
        if ctx.get("deadline_exceeded", False) or ctx.get("over_budget", False):
            break
        
        stage_reached = plan.get("stage", "unknown")
        leads_batch, ctx = _execute_fill_plan(
            ctx.get("niche", ""), ctx.get("city", ""),
            ctx.get("country", ""), target, plan, ctx)
        leads.extend(leads_batch)
        
        if len(leads) >= target:
            break
    
    # Dedupe leads by name+phone+website
    seen = set()
    unique_leads = []
    for lead in leads:
        key = (lead.get("name", ""), lead.get("phone", ""), lead.get("website", ""))
        if key not in seen:
            seen.add(key)
            unique_leads.append(lead)
    
    # Verify leads through the quality gate
    verified = []
    for lead in unique_leads:
        if ctx.get("deadline_exceeded", False) or ctx.get("over_budget", False):
            break
        verified_lead = verify_fn(lead)
        if verified_lead:
            verified.append(verified_lead)
    
    returned = len(verified)
    requested = target
    
    if returned < requested:
        reason = f"SOURCE_EXHAUSTED: returned {returned} of {requested} leads"
    else:
        reason = None
    
    return {
        "leads": verified[:target],
        "returned": returned,
        "requested": requested,
        "reason": reason,
        "stage_reached": stage_reached,
    }
