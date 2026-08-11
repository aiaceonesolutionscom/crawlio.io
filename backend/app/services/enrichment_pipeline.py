"""The enrichment pipeline: given a discovered lead (or an existing lead), fill
in the best contact data we can find from every free/paid source available.

Order of attack:
  1. Scrape the business's own website if it has one (plain HTTP or headless
     browser depending on plan) -- the most trustworthy source.
  2. If there's no website, ask Tavily for one, then scrape it.
  3. Whatever gaps remain (email/phone, or the whole profile for website-less
     leads) get a Tavily web search + AI extraction pass.
  4. If the website scrape produced ambiguous candidates, an AI disambiguation
     pass picks the real business contact.
  5. Social profiles are filled in via a Tavily lookup when the site didn't
     surface them.

Nothing here ever invents data: AI is only ever asked to read text we already
fetched from the web, and every extracted value is sanity-checked before it's
kept.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from app.services import (
    ai_extraction_service,
    browser_scraper_service,
    duckduckgo_service,
    geocoding_service,
    tavily_service,
    website_scraper_service,
)
from app.services.contact_extraction import collect_emails, collect_phones
from app.services.lead_quality import data_quality
from app.services.scrape_utils import normalize_website_url

logger = logging.getLogger(__name__)

_FILLABLE = ("email", "phone", "website", "address", "hours", "description", "social_links")


def _valid_email(email) -> bool:
    return bool(email) and len(collect_emails(email)) > 0


def _valid_phone(phone) -> bool:
    return bool(phone) and len(collect_phones(phone)) > 0


def _fill_gaps(result: dict, source: dict) -> None:
    for key in _FILLABLE:
        value = source.get(key)
        if value and not result.get(key):
            result[key] = value


def _merge_socials(result: dict, source) -> None:
    if not source:
        return
    merged = {**source, **(result.get("social_links") or {})}
    if merged:
        result["social_links"] = merged


async def _scrape_website(website: str, use_browser: bool, country_code: Optional[str]) -> dict:
    if use_browser:
        return await browser_scraper_service.extract_contact_from_website(website, country_code)
    return await website_scraper_service.extract_contact_from_website(website, country_code)


async def enrich_item(
    item: dict,
    *,
    city: str,
    country: str,
    country_code: Optional[str] = None,
    use_browser: bool = True,
    use_ai: bool = True,
) -> dict:
    """Enrich one discovered-lead dict (returns a new dict with enriched fields
    + quality metadata). Must be given at least `name`; city and country are
    needed for any web fallback."""
    result: dict = dict(item)
    name = result.get("name") or ""
    website = result.get("website") or ""
    sources: list[str] = []
    scraped: dict = {}

    if not name:
        result["enrichment_status"] = "failed"
        result["enrichment_error"] = "missing name"
        return result

    # 1) Scrape the business's own website.
    if website:
        try:
            scraped = await _scrape_website(website, use_browser, country_code)
        except Exception as exc:
            logger.warning("Enrichment website scrape failed for %s: %s", website, exc)
            scraped = {}
        if scraped:
            _fill_gaps(result, scraped)
            sources.append("website")
        website = result.get("website") or website

    # 2) No website (or scrape failed) -- ask Tavily then DuckDuckGo for one,
    #    then scrape it.
    if not website:
        found = None
        for lookup in (tavily_service.find_website_url, duckduckgo_service.find_website_url):
            try:
                found = await lookup(name, city, country)
            except Exception as exc:
                logger.warning("Enrichment website lookup failed for %s: %s", name, exc)
            if found:
                break
        if found:
            result["website"] = found
            website = found
            try:
                scraped = await _scrape_website(found, use_browser, country_code)
            except Exception as exc:
                logger.warning("Enrichment scrape of found site failed for %s: %s", found, exc)
                scraped = {}
            if scraped:
                _fill_gaps(result, scraped)
                sources.append("website")

    # 3) Gaps remain (or no website at all) -- Tavily + DuckDuckGo web search,
    #    then AI extraction.
    needs_web = use_ai and (not website or not (result.get("email") and result.get("phone")))
    if needs_web:
        web_results: list[dict] = []
        for search_fn in (tavily_service.enrich_business, duckduckgo_service.enrich_business):
            try:
                web_results += await search_fn(name, city, country)
            except Exception as exc:
                logger.warning("Enrichment web search failed for %s: %s", name, exc)
        if web_results:
            ai = await ai_extraction_service.extract_from_tavily_results(name, city, web_results)
            if ai:
                for key in ("email", "phone", "website", "address", "hours", "description", "social_links"):
                    value = ai.get(key)
                    if value and not result.get(key):
                        if key == "email" and not _valid_email(value):
                            continue
                        if key == "phone" and not _valid_phone(value):
                            continue
                        result[key] = value
                sources.append("web_search")

    # 4) AI disambiguation over the scraped own-website text.
    if use_ai and scraped and scraped.get("page_text"):
        try:
            ai = await ai_extraction_service.extract_contact(
                scraped["page_text"],
                name,
                city,
                website=result.get("website"),
                extra_socials=result.get("social_links") or {},
            )
        except Exception as exc:
            logger.warning("Enrichment AI disambiguation failed for %s: %s", name, exc)
            ai = {}
        if ai:
            confidence = ai.get("confidence") or 0.0
            ai_email = ai.get("email")
            if ai_email and _valid_email(ai_email) and (not result.get("email") or confidence >= 0.6):
                result["email"] = ai_email
            ai_phone = ai.get("phone")
            if ai_phone and _valid_phone(ai_phone) and (not result.get("phone") or confidence >= 0.6):
                result["phone"] = ai_phone
            for key in ("address", "hours", "description"):
                if ai.get(key) and not result.get(key):
                    result[key] = ai[key]
            if ai.get("website"):
                _fill_gaps(result, {"website": ai["website"]})
            _merge_socials(result, ai.get("social_links"))
            sources.append("ai")

    # 5) Fill missing social profiles via Tavily + DuckDuckGo. Always attempted
    #    for a website-less business — social media is often the ONLY contact
    #    channel they have — regardless of tier. For a business that does have
    #    a website, this stays a Pro-tier supplemental lookup. Both engines are
    #    queried and merged (not "stop at the first one that returns
    #    anything"), and a platform already found upstream is left alone
    #    rather than causing the whole search to be skipped.
    existing_socials = result.get("social_links") or {}
    # find_social_links only ever recognizes up to 4 platforms, so "still
    # missing something" is well-approximated by "found fewer than 4 so far."
    should_search_socials = (not website and len(existing_socials) < 4) or (use_ai and not existing_socials)
    if should_search_socials:
        socials: dict[str, str] = dict(existing_socials)
        for social_fn in (tavily_service.find_social_links, duckduckgo_service.find_social_links):
            try:
                found = await social_fn(name, city, country)
            except Exception as exc:
                logger.warning("Enrichment social lookup failed for %s: %s", name, exc)
                continue
            for platform, url in found.items():
                socials.setdefault(platform, url)
        if len(socials) > len(existing_socials):
            _merge_socials(result, socials)
            sources.append("social")

    # 6) Resolve a real coordinate via OpenStreetMap/Nominatim — previously no
    #    lat/lon was ever computed anywhere in this pipeline, so a lead's
    #    location was whatever bare city-name string discovery guessed (or
    #    nothing at all). Best-effort: a failed/empty geocode never blocks the
    #    rest of enrichment.
    try:
        geocoded = await geocoding_service.geocode_business(result.get("address"), city, country)
    except Exception as exc:
        logger.warning("Geocoding failed for %s: %s", name, exc)
        geocoded = None
    if geocoded:
        result["lat"] = geocoded["lat"]
        result["lon"] = geocoded["lon"]
        # Deliberately NOT overwriting result["address"] with Nominatim's
        # display_name: at city-level (the common case, when no real street
        # address was ever found) that's an administrative-area name like
        # "Karachi Division, Sindh, Pakistan" — longer and less useful than
        # the plain city name it would replace, not a more precise business
        # address. Coordinates are still stored for map use either way.
        sources.append("geocoding")

    result["social_links"] = result.get("social_links") or {}
    if result.get("website"):
        result["website"] = normalize_website_url(result["website"])
    result["completeness"] = data_quality(result)
    result["enrichment_status"] = "done"
    result["enrichment_source"] = ", ".join(dict.fromkeys(sources)) or None
    result["last_enriched_at"] = datetime.now(timezone.utc).isoformat()
    result.pop("enrichment_error", None)
    return result
