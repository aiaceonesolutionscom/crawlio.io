import asyncio
import logging
from typing import Optional
from urllib.parse import urljoin

import httpx

from app.services.scrape_utils import aggregate_contacts, discover_contact_urls, normalize_website_url

logger = logging.getLogger(__name__)

SCRAPE_TIMEOUT = 8.0
SCRAPE_HEADERS = {
    # A real browser UA -- some small-business hosting (Wix, GoDaddy sites) 406s
    # bare httpx/requests-style user agents, same class of issue seen with Overpass.
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
}
# How many same-origin pages (homepage + discovered contact pages) to fetch max.
MAX_PAGES_PER_SITE = 8
# How many of those subpages to fetch at once -- they're the same origin, so a
# handful in parallel is a normal browsing pattern, not a burst; this is what
# actually cuts per-lead wall time instead of paying up to MAX_PAGES_PER_SITE
# timeouts back to back.
SUBPAGE_CONCURRENCY = 4


async def _fetch_html(client: httpx.AsyncClient, url: str) -> str:
    try:
        resp = await client.get(url)
    except httpx.HTTPError as exc:
        logger.info("Website scrape failed for %s: %s", url, exc)
        return ""
    if resp.status_code >= 400 or "text/html" not in resp.headers.get("content-type", ""):
        return ""
    return resp.text


async def _scrape_urls(client: httpx.AsyncClient, urls: list[str]) -> list[str]:
    """Fetch a list of same-origin URLs concurrently (bounded), returning
    whatever HTML came back, homepage-then-subpages order. A dead subpath is
    skipped silently; the homepage failing means the site is down."""
    semaphore = asyncio.Semaphore(SUBPAGE_CONCURRENCY)

    async def _bounded(url: str) -> str:
        async with semaphore:
            return await _fetch_html(client, url)

    htmls = await asyncio.gather(*(_bounded(url) for url in urls[:MAX_PAGES_PER_SITE]))
    return [html for html in htmls if html]


async def _browser_fallback(target: str, country_code: Optional[str]) -> dict:
    try:
        from app.services import browser_scraper_service

        return await browser_scraper_service.extract_contact_from_website(target, country_code)
    except Exception as exc:
        logger.info("Browser fallback failed for %s: %s", target, exc)
        return {}


def _aggregate(pages: list[str], target: str, country_code: Optional[str]) -> dict:
    result = aggregate_contacts(pages, website=target, country_code=country_code)
    return {
        "email": result.get("email"),
        "phone": result.get("phone"),
        "website": normalize_website_url(result.get("website") or target) or None,
        "address": result.get("address"),
        "hours": result.get("hours"),
        "description": result.get("description"),
        "social_links": result.get("social_links") or {},
        "email_candidates": result.get("email_candidates") or [],
        "phone_candidates": result.get("phone_candidates") or [],
        "page_text": result.get("page_text") or "",
    }


async def fetch_plain(
    url: str,
    country_code: Optional[str] = None,
    max_pages: int = MAX_PAGES_PER_SITE,
) -> Optional[dict]:
    """Phase 1 only: plain-HTTP homepage + subpages, no browser fallback.
    Returns None when the homepage came back empty (JS-only SPA, bot-wall 403,
    or a slow/blocked host) — the caller decides what to do about that (a
    single-site browser attempt via extract_contact_from_website, or batching
    many such URLs through one shared browser via enrichment_pipeline's batch
    path, which is what actually matters when several leads in one search all
    need it — one browser launch per lead is the dominant cost otherwise)."""
    target = normalize_website_url(url)
    if not target:
        return None

    async with httpx.AsyncClient(
        timeout=SCRAPE_TIMEOUT, headers=SCRAPE_HEADERS, follow_redirects=True
    ) as client:
        home_html = await _fetch_html(client, target)
        if not home_html:
            return None

        sub_urls = discover_contact_urls(target, home_html, max_urls=max_pages)
        sub_pages = await _scrape_urls(client, sub_urls)
        pages = [home_html, *sub_pages]

    return _aggregate(pages, target, country_code)


async def extract_contact_from_website(
    url: str,
    country_code: Optional[str] = None,
    max_pages: int = MAX_PAGES_PER_SITE,
) -> dict:
    """Fetch a business's own website (homepage, then crawled contact/about
    pages) and pull whatever contact info + social links are on them -- free, no
    API key, and low-risk since it's a GET to public pages the business itself
    put up (not scraping a search engine). Emails/phones are ranked, not just
    first-match, and mailto/tel links + JSON-LD are preferred signals.

    Single-site convenience wrapper around fetch_plain + a one-off browser
    fallback; for enriching many leads at once, prefer
    enrichment_pipeline.enrich_items_batch, which batches every fallback
    through one shared browser instead of one launch per site."""
    target = normalize_website_url(url)
    if not target:
        return {}

    result = await fetch_plain(target, country_code, max_pages)
    if result is not None:
        return result

    # Plain HTTP got nothing back at all. This used to just give up here
    # regardless of tier; now every tier gets one real-browser attempt as a
    # reliability floor before we accept "no data" for a site that might just
    # need JS to render.
    return await _browser_fallback(target, country_code)
