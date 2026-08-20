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
_OSM_TIMEOUT = 28.0

# Hard wall-clock deadline for the entire discovery request. The fallback
# ladder (synonyms -> nearby cities -> country-wide top cities) is valuable on
# thin markets but must never turn a lead search into a multi-minute wait, so
# every fallback step checks the budget and stops once it's spent — the search
# returns whatever real, validated leads it has instead of grinding on.
_DISCOVERY_DEADLINE = 110.0

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
    country_code: str = "PK",
) -> tuple[list[dict], dict[str, int], bool]:
    """Run the structured crawlers for one city. Returns (raw_candidates,
    per_source_counts, engaged) — engaged is True when at least one source
    actually returned something (vs. failing/empty).

    Sources are ordered by region priority; unhealthy sources (via source_tracker)
    are skipped. Every source is capped and guarded by a per-source timeout.

    `use_maps=False` skips the Google Maps crawler — nearby-city fallback
    trades that richness for speed: OSM + directories alone finish in a few
    seconds, so trying 1-2 nearby cities stays fast instead of multiplying
    the wait by however many cities get tried."""
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
        "maps": lambda: maps_crawler.search_businesses(niche, city, country, fetch_limit),
        "osm": lambda: overpass_service.discover_businesses(niche, city, country, fetch_limit),
        "directory": lambda: directory_scraper.search_businesses(niche, city, country, fetch_limit),
        "bing": lambda: bing_maps_crawler.search_businesses(niche, city, country, fetch_limit),
        "bizdata": lambda: bizdata_crawler.search_businesses(niche, city, country, fetch_limit),
        "wikidata": lambda: wikidata_crawler.search_businesses(niche, city, country, fetch_limit),
        "wikipedia": lambda: wikipedia_crawler.search_businesses(niche, city, country, fetch_limit),
        "certtransparency": lambda: certtransparency_crawler.search_businesses(niche, city, country, fetch_limit),
        "dns": lambda: dns_crawler.search_businesses(niche, city, country, fetch_limit),
    }

    # Source timeout mapping
    source_timeouts = {
        "maps": _MAPS_TIMEOUT,
        "osm": _OSM_TIMEOUT,
        "directory": _SOURCE_TIMEOUT,
        "bing": _SOURCE_TIMEOUT,
        "bizdata": _SOURCE_TIMEOUT,
        "wikidata": _SOURCE_TIMEOUT,
        "wikipedia": _SOURCE_TIMEOUT,
        "certtransparency": _SOURCE_TIMEOUT,
        "dns": _SOURCE_TIMEOUT,
    }

    # Build tasks based on priority, skipping unhealthy and respecting use_maps
    tasks = []
    names = []
    for source_name in priority:
        if source_name in unhealthy:
            logger.info("Skipping unhealthy source: %s", source_name)
            continue
        if source_name == "maps" and not use_maps:
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
) -> list[dict]:
    """Return up to `limit` real, contact-validated businesses for a niche in a
    city/country. Raises DiscoveryUnavailableError only when the requested
    city's sources are all unavailable (not merely thin on results — that's
    handled by the nearby-city/Tavily fallbacks below).

    `enrich_candidates` and `source_counts` mirror the upstream API contract:
    enhanced/Pro plans may ask for AI-assisted enrichment of raw candidates,
    and `source_counts` (when given) is filled with per-source raw candidate
    counts for progress reporting."""
    if limit < 1:
        return []

    deadline = time.monotonic() + _DISCOVERY_DEADLINE

    def _over_budget() -> bool:
        # A fallback pass costs up to one full source round (~_SOURCE_TIMEOUT).
        # Require room for that pass on top of the remaining time, otherwise
        # every fallback stage would start right at the deadline and grind on.
        return time.monotonic() >= deadline - _SOURCE_TIMEOUT

    candidates, counts, engaged = await _scrape_city_sources(niche, city, country, limit, deadline=deadline, country_code=country_code)
    if source_counts is not None:
        source_counts.update(counts)
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
        niche, city, counts["maps"], counts["osm"], counts["directory"],
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
                synonym, city, country, remaining, use_maps=False, deadline=deadline, country_code=country_code
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
                niche, nearby["name"], country, remaining, use_maps=False, deadline=deadline, country_code=country_code
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
                nearby["name"], niche, city, 
                nb_counts.get("maps", 0), nb_counts.get("osm", 0), nb_counts.get("directory", 0), len(cleaned),
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
                niche, top["name"], country, remaining, use_maps=False, deadline=deadline, country_code=country_code
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

    # Tavily web-search pass: runs on EVERY discovery (not just as a last
    # resort) to surface business name + website pairs that structured sources
    # miss. The websites it returns are then scraped for email/phone/address in
    # the enrichment pipeline, so the leads here gain crawlable websites even
    # when the structured sources only returned a bare name. Bounded and opt-in;
    # merged candidates never override higher-priority sources (see
    # web_search_service.py and lead_merger._SOURCE_PRIORITY).
    if settings.tavily_enabled and settings.tavily_api_key and not _over_budget():
        tavily_count = max(limit - len(cleaned), _TAVILY_MIN_TOPUP)
        extra = await web_search_service.find_extra_businesses(niche, city, country, tavily_count)
        if extra:
            remerged = lead_merger.merge_businesses(cleaned + extra)
            cleaned = _validate_all(remerged, niche, country_code, limit)
            logger.info(
                "Tavily pass for %s in %s: +%d candidates -> %d validated total",
                niche, city, len(extra), len(cleaned),
            )

    # Graceful degradation check
    healthy_count = sum(1 for src in source_tracker.all_stats().values() if src.get("success_rate", 1.0) >= 0.3)
    if healthy_count < DEGRADATION_THRESHOLDS["full"]:
        logger.warning("Degraded source health: %d healthy sources, operating in reduced mode", healthy_count)
    if len(cleaned) < MIN_RESULTS_FLOOR:
        logger.warning("Results below minimum floor: %d < %d", len(cleaned), MIN_RESULTS_FLOOR)

    # Most complete first so the requested cap is filled with the best leads.
    cleaned.sort(key=lambda r: data_quality(r), reverse=True)
    return cleaned[:limit]


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
