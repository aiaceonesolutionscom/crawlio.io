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
    """Fetch a list of same-origin URLs, returning their HTML in order. A dead
    subpath is skipped silently; the homepage failing means the site is down."""
    pages: list[str] = []
    for url in urls[:MAX_PAGES_PER_SITE]:
        html = await _fetch_html(client, url)
        if html:
            pages.append(html)
    return pages


async def extract_contact_from_website(
    url: str,
    country_code: Optional[str] = None,
    max_pages: int = MAX_PAGES_PER_SITE,
) -> dict:
    """Fetch a business's own website (homepage, then crawled contact/about
    pages) and pull whatever contact info + social links are on them -- free, no
    API key, and low-risk since it's a GET to public pages the business itself
    put up (not scraping a search engine). Emails/phones are ranked, not just
    first-match, and mailto/tel links + JSON-LD are preferred signals."""
    target = normalize_website_url(url)
    if not target:
        return {}

    async with httpx.AsyncClient(
        timeout=SCRAPE_TIMEOUT, headers=SCRAPE_HEADERS, follow_redirects=True
    ) as client:
        home_html = await _fetch_html(client, target)
        if not home_html:
            return {}

        sub_urls = discover_contact_urls(target, home_html, max_urls=max_pages)
        sub_pages = await _scrape_urls(client, sub_urls)
        pages = [home_html, *sub_pages]

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
