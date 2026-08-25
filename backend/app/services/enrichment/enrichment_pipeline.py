"""The enrichment pipeline: fill a discovered (or saved) lead's remaining gaps
using only *real* data — no AI guessing, no paid web-search APIs.

Order of attack:
  1. If the business has a website, scrape it (plain HTTP, or headless browser
     depending on plan) for email, socials, hours, description and address.
  2. Whatever email the site published is MX-verified before it's kept.
  3. If lat/lon are still missing, resolve them via OSM/Nominatim geocoding.

Nothing here invents data: every value either comes from the business's own
published page or from a geocoder, and every email is checked for deliverability.

`enrich_item` handles one lead; `enrich_items_batch` handles many at once and
is the one that actually matters for request latency — a headless-browser
launch is the expensive part (seconds, not milliseconds) and enrich_item's own
website scrape launches a fresh one per call. Calling enrich_item in a loop
over N leads means N separate browser launches; enrich_items_batch instead
funnels every browser-needing site in the batch through ONE shared browser
(browser_scraper_service.extract_contact_details already supports this).
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from app.services.discovery import browser_scraper_service, geocoding_service, website_scraper_service
from app.services.discovery.crawlers import maps_crawler
from app.services.discovery.crawlers.lead_validator import validate_email
from app.services.lead.lead_quality import data_quality

from app.services.discovery.scrape_utils import normalize_website_url


logger = logging.getLogger(__name__)

_FILLABLE = ("email", "phone", "website", "address", "hours", "description", "social_links")

# Google Maps name-lookups are one Playwright crawl each; cap how many run in
# a single inline batch so enrichment stays bounded when the worker is down.
# The background worker enriches item-by-item and is not bound by this cap.
MAPS_LOOKUP_CAP = 10


def _fill_gaps(result: dict, source: dict) -> None:
    for key in _FILLABLE:
        value = source.get(key)
        if value and not result.get(key):
            result[key] = value


async def _maps_lookup(item: dict, city: str, country: str) -> Optional[dict]:
    """Look up a lead's real GBP panel data on Google Maps by its name, filling
    the phone/website/address/hours the free structured sources (OSM,
    directories) don't carry. Returns the raw Maps record or None; never
    raises. Only used when the caller opts in via use_google_maps."""
    name = (item.get("name") or "").strip()
    if not name:
        return None
    try:
        return await maps_crawler.lookup_business_by_name(name, city, country)
    except Exception as exc:
        logger.warning("Google Maps enrichment lookup failed for %s: %s", name, exc)
        return None


async def _scrape_website(website: str, use_browser: bool, country_code: Optional[str]) -> dict:
    if use_browser:
        return await browser_scraper_service.extract_contact_from_website(website, country_code)
    return await website_scraper_service.extract_contact_from_website(website, country_code)


async def _finalize(result: dict, scraped: dict, sources: list[str], city: str, country: str) -> dict:
    """Steps shared by every lead regardless of how its website scrape (if
    any) was obtained: MX-verify the email, geocode if lat/lon still missing,
    then stamp completeness/status metadata."""
    name = result.get("name") or ""

    # Only keep an email that is actually deliverable (MX-verified).
    if result.get("email"):
        verified = validate_email(result["email"])
        result["email"] = verified
    elif scraped and scraped.get("email_candidates"):
        # No confident email, but the site did publish candidates — take the
        # first one that validates so a low-signal page still yields a contact.
        for candidate in scraped["email_candidates"]:
            verified = validate_email(candidate)
            if verified:
                result["email"] = verified
                sources.append("website_email")
                break

    # Resolve a real coordinate when none is known yet.
    if result.get("lat") is None or result.get("lon") is None:
        try:
            geocoded = await geocoding_service.geocode_business(result.get("address"), city, country)
        except Exception as exc:
            logger.warning("Geocoding failed for %s: %s", name, exc)
            geocoded = None
        if geocoded:
            result["lat"] = geocoded["lat"]
            result["lon"] = geocoded["lon"]
            sources.append("geocoding")

    # Add scrape_note based on scrape outcome
    if result.get("website"):
        if not scraped:
            result["scrape_note"] = "no_website_content_fetched"
        elif not scraped.get("_scraped_ok", True):
            # Scraper had an error (timeout, blocked, etc.)
            err = scraped.get("_scrape_error", "unknown_error")
            result["scrape_note"] = f"website_unreachable: {err}"
        elif not any(scraped.get(f) for f in ("email", "phone", "address", "social_links")):
            # Page loaded but no contact info found
            result["scrape_note"] = "site_loaded_no_contact_published"
        else:
            # Successful scrape with some contact data
            found = []
            if scraped.get("email"): found.append("email")
            if scraped.get("phone"): found.append("phone")
            if scraped.get("social_links"): found.append("social")
            if scraped.get("address"): found.append("address")
            result["scrape_note"] = f"scraped_ok: {', '.join(found) if found else 'page_only'}"

    result["social_links"] = result.get("social_links") or {}
    if result.get("website"):
        result["website"] = normalize_website_url(result["website"])
    result["completeness"] = data_quality(result)
    result["enrichment_status"] = "done"
    result["enrichment_source"] = ", ".join(dict.fromkeys(sources)) or None
    result["last_enriched_at"] = datetime.now(timezone.utc).isoformat()
    result.pop("enrichment_error", None)
    return result


async def enrich_item(
    item: dict,
    *,
    city: str,
    country: str,
    country_code: Optional[str] = None,
    use_browser: bool = True,
    use_ai: bool = True,
    use_google_maps: bool = False,
    enable_website_scraping: bool = True,
    enable_phone_enrichment: bool = True,
    enable_email_enrichment: bool = True,
    enable_address_enrichment: bool = True,
    enable_social_media: bool = False,
) -> dict:
    """Enrich one lead dict in place of the old AI pipeline. Returns a new dict
    with enriched fields + quality metadata. Never raises.

    Enriching many leads at once (e.g. a fresh discovery batch)? Prefer
    enrich_items_batch instead — calling this in a loop launches one browser
    per lead when use_browser is True or a site needs the browser fallback;
    the batch version shares one browser across the whole batch."""
    result: dict = dict(item)
    name = result.get("name") or ""
    website = result.get("website") or ""
    sources: list[str] = []

    if not name:
        result["enrichment_status"] = "failed"
        result["enrichment_error"] = "missing name"
        return result

    # 1. Google Maps name-lookup FIRST: fills the phone/website/email/address
    #    the free structured sources (OSM, directories) don't carry. Runs when
    #    ANY contact channel is missing (not just when both phone+website are
    #    absent), so a lead with a phone but no website/email still gets its
    #    GBP panel pulled.
    if use_google_maps and enable_phone_enrichment and not (result.get("phone") and result.get("website") and result.get("email")):
        maps_record = await _maps_lookup(result, city, country)
        if maps_record:
            _fill_gaps(result, maps_record)
            sources.append("google_maps")
            website = result.get("website") or website

    # 2. Website scrape pass: ONLY if enable_website_scraping is True
    scraped: dict = {}
    if website and enable_website_scraping:
        try:
            scraped = await _scrape_website(website, use_browser, country_code)
        except Exception as exc:
            logger.warning("Enrichment website scrape failed for %s: %s", website, exc)
            scraped = {}
        if scraped:
            # Only fill gaps for fields that are enabled
            if enable_email_enrichment and scraped.get("email"):
                result["email"] = scraped["email"]
            if enable_phone_enrichment and scraped.get("phone"):
                result["phone"] = scraped["phone"]
            if enable_address_enrichment and scraped.get("address"):
                result["address"] = scraped["address"]
            if enable_social_media and scraped.get("social_links"):
                result["social_links"] = {**result.get("social_links", {}), **scraped["social_links"]}
            if scraped.get("hours"):
                result["hours"] = scraped["hours"]
            if scraped.get("description"):
                result["description"] = scraped["description"]
            sources.append("website")

    return await _finalize(result, scraped, sources, city, country)


async def enrich_items_batch(
    items: list[dict],
    *,
    city: str,
    country: str,
    country_code: Optional[str] = None,
    use_browser: bool = True,
    use_ai: bool = True,
    use_google_maps: bool = False,
    enable_website_scraping: bool = True,
    enable_phone_enrichment: bool = True,
    enable_email_enrichment: bool = True,
    enable_address_enrichment: bool = True,
    enable_social_media: bool = False,
) -> list[dict]:
    """Batch version of enrich_item — same output shape, but every lead in
    `items` that needs a headless-browser scrape shares ONE browser instance
    instead of each launching its own. That's the dominant latency cost when
    enriching many leads synchronously (e.g. inline enrichment when no
    background worker is available), so this is what actually matters for
    request latency, not just a micro-optimization."""
    results = [dict(item) for item in items]
    sources_by_index: dict[int, list[str]] = {i: [] for i in range(len(results))}
    scraped_by_index: dict[int, dict] = {}

    # 1. Google Maps name-lookup pass FIRST: for every lead missing ANY contact
    #    channel (phone/website/email), pull its real GBP panel data by name.
    #    Sequential (one Playwright lookup per lead), bounded by MAPS_LOOKUP_CAP
    #    to keep the batch's latency sane. This runs before the website pass so
    #    any website the GBP panel reveals gets scraped below.
    if use_google_maps and enable_phone_enrichment:
        looked_up = 0
        for i, result in enumerate(results):
            if looked_up >= MAPS_LOOKUP_CAP:
                break
            if not result.get("name"):
                continue
            if result.get("phone") and result.get("website") and result.get("email"):
                continue
            maps_record = await _maps_lookup(result, city, country)
            looked_up += 1
            if maps_record:
                _fill_gaps(result, maps_record)
                sources_by_index[i].append("google_maps")

    # 2. Website scrape pass over EVERY website the leads now carry — ONLY if enable_website_scraping is True
    websites = [(r.get("website") or "") if r.get("name") else "" for r in results]

    if use_browser and enable_website_scraping:
        # Every website-having lead goes through one shared browser.
        urls = [w for w in websites if w]
        if urls:
            try:
                batch = await browser_scraper_service.extract_contact_details(urls, country_code)
            except Exception as exc:
                logger.warning("Batch browser enrichment failed: %s", exc)
                batch = [{} for _ in urls]
            url_to_result = dict(zip(urls, batch))
            for i, website in enumerate(websites):
                if website and url_to_result.get(website):
                    scraped_by_index[i] = url_to_result[website]
                    sources_by_index[i].append("website")
    else:
        # Free tier: try plain HTTP for every site concurrently first (cheap,
        # no browser), then batch only the ones that came back empty through
        # one shared browser instead of one launch per lead.
        async def _try_plain(website: str) -> Optional[dict]:
            if not website:
                return None
            try:
                return await website_scraper_service.fetch_plain(website, country_code)
            except Exception as exc:
                logger.warning("Enrichment website scrape failed for %s: %s", website, exc)
                return {}

        plain_results = await asyncio.gather(*(_try_plain(w) for w in websites))

        fallback_indices: list[int] = []
        fallback_urls: list[str] = []
        for i, (website, plain) in enumerate(zip(websites, plain_results)):
            if not website:
                continue
            if plain:
                scraped_by_index[i] = plain
                sources_by_index[i].append("website")
            elif plain is None:
                fallback_indices.append(i)
                fallback_urls.append(website)

        if fallback_urls:
            try:
                batch = await browser_scraper_service.extract_contact_details(fallback_urls, country_code)
            except Exception as exc:
                logger.warning("Batch browser fallback failed: %s", exc)
                batch = [{} for _ in fallback_urls]
            for i, scraped in zip(fallback_indices, batch):
                if scraped:
                    scraped_by_index[i] = scraped
                    sources_by_index[i].append("website")

    for i, result in enumerate(results):
        name = result.get("name") or ""
        if not name:
            result["enrichment_status"] = "failed"
            result["enrichment_error"] = "missing name"
            continue
        scraped = scraped_by_index.get(i, {})
        if scraped:
            # Only fill gaps for enabled fields
            if enable_email_enrichment and scraped.get("email"):
                result["email"] = scraped["email"]
            if enable_phone_enrichment and scraped.get("phone"):
                result["phone"] = scraped["phone"]
            if enable_address_enrichment and scraped.get("address"):
                result["address"] = scraped["address"]
            if enable_social_media and scraped.get("social_links"):
                result["social_links"] = {**result.get("social_links", {}), **scraped["social_links"]}
            if scraped.get("hours"):
                result["hours"] = scraped["hours"]
            if scraped.get("description"):
                result["description"] = scraped["description"]
            sources_by_index[i].append("website")
        results[i] = await _finalize(result, scraped, sources_by_index[i], city, country)

    return results
