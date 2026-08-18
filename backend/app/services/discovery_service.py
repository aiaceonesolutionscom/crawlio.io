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
from app.services import geo_service, overpass_service
from app.services.crawlers import (
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
from app.services.crawlers.base import source_tracker
from app.services.contact_extraction import clean_business_name, is_own_website
from app.services.lead_quality import data_quality

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
# Timeout per individual source so one slow/straggler source doesn't stall
# the whole request (e.g. a Google Maps hiccup blocking for 30s+).
_SOURCE_TIMEOUT = 12.0

# Google Maps is the primary, richest source (phone + website + rating) but is
# also the slowest: a Playwright crawl needs ~40s+ for a useful panel set. It
# gets its own dedicated budget so the 12s fast-source guard doesn't cancel it
# mid-crawl (which previously starved every search to ~13-19 leads).
_MAPS_TIMEOUT = 35.0

# OSM/Overpass races several mirrors against a free shared API; a single query
# routinely takes ~15-25s to come back (mirrors 504/429 under load). It is the
# most reliable volume source, so it also gets a dedicated budget instead of the
# 12s fast-source guard that kept cancelling it and collapsing searches to
# directory+bizdata only (~18 leads).
_OSM_TIMEOUT = 28.0

# Hard wall-clock deadline for the entire discovery request. The fallback
# ladder (synonyms -> nearby cities -> country-wide top cities) is valuable on
# thin markets but must never turn a lead search into a multi-minute wait, so
# every fallback step checks the budget and stops once it's spent — the search
# returns whatever real, validated leads it has instead of grinding on.
_DISCOVERY_DEADLINE = 110.0


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
    niche: str, city: str, country: str, limit: int, use_maps: bool = True,
    deadline: Optional[float] = None,
) -> tuple[list[dict], dict[str, int], bool]:
    """Run the structured crawlers for one city. Returns (raw_candidates,
    per_source_counts, engaged) — engaged is True when at least one source
    actually returned something (vs. failing/empty).

    Every source is capped at `min(limit, PER_SOURCE_FETCH_CAP)` and guarded
    by a per-source timeout so a single slow crawler can't stall the request.

    Order of attempts (first to last):
      1. Google Maps (primary, if use_maps=True) — richest data, slowest.
      2. OSM/Overpass (structured POIs, free).
      3. Free Pakistan directories (extra businesses, some emails).
      4. Wikidata (structured entities from the linked open data cloud).
      5. Wikipedia (articles about organizations/places in the niche).
      6. CertTransparency (CT-log entries revealing organizational domains).
      7. DNS (enumerated subdomains and hostnames).

    `use_maps=False` skips the Google Maps crawler — nearby-city fallback
    trades that richness for speed: OSM + directories alone finish in a few
    seconds, so trying 1-2 nearby cities stays fast instead of multiplying
    the wait by however many cities get tried."""
    fetch_limit = min(max(limit, 1) * OVERSAMPLE_FACTOR, PER_SOURCE_FETCH_CAP)

    tasks = [
        _timed_source("osm", overpass_service.discover_businesses(niche, city, country, fetch_limit), deadline, timeout=_OSM_TIMEOUT),
        _timed_source("directory", directory_scraper.search_businesses(niche, city, country, fetch_limit), deadline),
        _timed_source("bing", bing_maps_crawler.search_businesses(niche, city, country, fetch_limit), deadline),
        _timed_source("bizdata", bizdata_crawler.search_businesses(niche, city, country, fetch_limit), deadline),
    ]
    names = ["osm", "directory", "bing", "bizdata"]

    if use_maps:
        tasks.insert(0, _timed_source("maps", maps_crawler.search_businesses(niche, city, country, fetch_limit), deadline, timeout=_MAPS_TIMEOUT))
        names.insert(0, "maps")

    # New providers: Wikidata, Wikipedia, CertTransparency, DNS.
    # These are added after the core three; they are lighter weight and
    # serve as supplementary sources when the primary ones are thin.
    tasks.extend([
        _timed_source("wikidata", wikidata_crawler.search_businesses(niche, city, country, fetch_limit), deadline),
        _timed_source("wikipedia", wikipedia_crawler.search_businesses(niche, city, country, fetch_limit), deadline),
        _timed_source("certtransparency", certtransparency_crawler.search_businesses(niche, city, country, fetch_limit), deadline),
        _timed_source("dns", dns_crawler.search_businesses(niche, city, country, fetch_limit), deadline),
    ])
    names.extend(["wikidata", "wikipedia", "certtransparency", "dns"])

    outcomes = await asyncio.gather(*tasks, return_exceptions=True)

    source_counts: dict[str, int] = {
        "maps": 0, "osm": 0, "directory": 0, "bing": 0, "bizdata": 0,
        "wikidata": 0, "wikipedia": 0, "certtransparency": 0, "dns": 0,
    }
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
) -> list[dict]:
    """Return up to `limit` real, contact-validated businesses for a niche in a
    city/country. Raises DiscoveryUnavailableError only when the requested
    city's sources are all unavailable (not merely thin on results — that's
    handled by the nearby-city/Tavily fallbacks below)."""
    if limit < 1:
        return []

    deadline = time.monotonic() + _DISCOVERY_DEADLINE

    def _over_budget() -> bool:
        # A fallback pass costs up to one full source round (~_SOURCE_TIMEOUT).
        # Require room for that pass on top of the remaining time, otherwise
        # every fallback stage would start right at the deadline and grind on.
        return time.monotonic() >= deadline - _SOURCE_TIMEOUT

    candidates, source_counts, engaged = await _scrape_city_sources(niche, city, country, limit, deadline=deadline)
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

    # If oversampled sources still didn't yield enough valid leads, retry
    # Overpass (the fast, free source) within the same city but with an
    # escalated search radius before falling back to nearby cities. This
    # catches businesses just outside the default Overpass bbox but still
    # legitimately in the requested city, and it's cheap (no Playwright).
    if len(cleaned) < limit and not _over_budget():
        remaining = limit - len(cleaned)
        extra_budget = min(remaining * OVERSAMPLE_FACTOR, PER_SOURCE_FETCH_CAP)
        try:
            overpass_extra = await asyncio.wait_for(
                overpass_service.discover_businesses(niche, city, country, extra_budget, wider_radius=True),
                timeout=max(deadline - time.monotonic(), 0.1),
            )
        except (asyncio.TimeoutError, Exception) as exc:
            logger.info("Overpass wider-radius retry for %s in %s skipped: %s", niche, city, exc)
            overpass_extra = []

        if overpass_extra:
            for item in overpass_extra:
                item.setdefault("result_city", city)
                item.setdefault("is_fallback_city", False)
            candidates.extend(overpass_extra)
            merged = lead_merger.merge_businesses(candidates)
            cleaned = _validate_all(merged, niche, country_code, limit)
            logger.info(
                "Overpass wider-radius top-up for %s in %s: +%d raw -> %d validated total",
                niche, city, len(overpass_extra), len(cleaned),
            )

    # --- Fill ladder: synonym expansion within the primary city --------------
    # Same city, but every source queried with each synonym the niche expands
    # to. Directories/aggregators index different phrases; a "dental clinic"
    # query surfaces listings "dentist" misses, and vice versa. Real structured
    # data, same city, still cheaper than a nearby city (no new geography).
    if len(cleaned) < limit and not _over_budget():
        synonyms = [s for s in niche_synonyms.expand_synonyms(niche) if s.lower() != niche.strip().lower()]
        for synonym in synonyms[:3]:
            if len(cleaned) >= limit or _over_budget():
                break
            remaining = limit - len(cleaned)
            syn_candidates, syn_counts, syn_engaged = await _scrape_city_sources(
                synonym, city, country, remaining, use_maps=False, deadline=deadline
            )
            if not syn_engaged:
                continue
            for item in syn_candidates:
                item["result_city"] = city
                item["is_fallback_city"] = True
                item["original_niche"] = niche
            candidates.extend(syn_candidates)
            merged = lead_merger.merge_businesses(candidates)
            cleaned = _validate_all(merged, niche, country_code, limit)
            logger.info(
                "Synonym top-up %r for %s in %s: +%d raw -> %d validated total",
                synonym, niche, city, len(syn_candidates), len(cleaned),
            )

    # Nearby-city fallback: only engages when the *primary* city's sources are
    # healthy but genuinely thin on results (e.g. Islamabad vs. Karachi) — real
    # structured data from a real nearby city, not a stub, tried before Tavily.
    if len(cleaned) < limit and not _over_budget():
        for nearby in geo_service.nearby_cities(country_code, city, n=_NEARBY_CITY_FALLBACKS):
            if len(cleaned) >= limit or _over_budget():
                break
            remaining = limit - len(cleaned)
            nb_candidates, nb_counts, nb_engaged = await _scrape_city_sources(
                niche, nearby["name"], country, remaining, use_maps=False, deadline=deadline
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

    # Country-wide fallback: when even nearby cities are thin (rare micro-city
    # searches in a country with few businesses of the niche), try the country's
    # top cities — real businesses a user is still happy to see, with
    # result_city + is_fallback_city tagged honestly.
    if len(cleaned) < limit and not _over_budget():
        top_cities = geo_service.top_cities(country_code, n=_COUNTRY_TOP_CITIES_FALLBACKS)
        for top in top_cities:
            if len(cleaned) >= limit or _over_budget() or (top.get("name") or "").lower() == (city or "").lower():
                continue
            remaining = limit - len(cleaned)
            tc_candidates, tc_counts, tc_engaged = await _scrape_city_sources(
                niche, top["name"], country, remaining, use_maps=False, deadline=deadline
            )
            if not tc_engaged:
                continue
            for item in tc_candidates:
                item["result_city"] = top["name"]
                item["is_fallback_city"] = True
            candidates.extend(tc_candidates)
            merged = lead_merger.merge_businesses(candidates)
            cleaned = _validate_all(merged, niche, country_code, limit)
            logger.info(
                "Country-wide fallback %s for %s (requested %s): +%d raw -> %d validated total",
                top["name"], niche, city, len(tc_candidates), len(cleaned),
            )

    # Last-resort, opt-in top-up when everything above still came up short —
    # never runs otherwise, and never overrides anything already found (see
    # web_search_service.py and lead_merger._SOURCE_PRIORITY).
    if settings.tavily_enabled and settings.tavily_api_key and len(cleaned) < limit and not _over_budget():
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
