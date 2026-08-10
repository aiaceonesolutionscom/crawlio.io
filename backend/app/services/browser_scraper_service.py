import asyncio
import logging
from typing import Optional
from urllib.parse import urljoin

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright

from app.services.scrape_utils import aggregate_contacts, discover_contact_urls, normalize_website_url

logger = logging.getLogger(__name__)

NAV_TIMEOUT_MS = 12_000
# Real-browser navigation can still be mid-render right after "domcontentloaded"
# fires (JS-injected footers, cookie-consent-gated content) -- a short settle
# window catches most of that without waiting for full network idle, which
# some sites (ad trackers, chat widgets) never actually reach.
SETTLE_MS = 400
# Each concurrent scrape holds open a browser page/tab; unbounded concurrency
# against a large batch would spike memory and can trip site-side rate limits.
MAX_CONCURRENT_PAGES = 6
MAX_PAGES_PER_SITE = 8
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


async def _scrape_one(context, url: str, country_code: Optional[str]) -> dict:
    """Navigate a single business site: homepage, then discovered contact
    subpages, and aggregate ranked contacts across whatever loaded."""
    target = normalize_website_url(url)
    if not target:
        return {}

    page = await context.new_page()
    pages_html: list[str] = []
    home_loaded = False
    try:
        try:
            await page.goto(target, timeout=NAV_TIMEOUT_MS, wait_until="domcontentloaded")
            await page.wait_for_timeout(SETTLE_MS)
            home_html = await page.content()
            pages_html.append(home_html)
            home_loaded = True
        except PlaywrightError:
            pass

        if home_loaded:
            sub_urls = discover_contact_urls(target, pages_html[0], max_urls=MAX_PAGES_PER_SITE)
            for sub_url in sub_urls[:MAX_PAGES_PER_SITE]:
                try:
                    await page.goto(urljoin(target, sub_url), timeout=NAV_TIMEOUT_MS, wait_until="domcontentloaded")
                    await page.wait_for_timeout(SETTLE_MS)
                    html = await page.content()
                    if html and html not in pages_html:
                        pages_html.append(html)
                except PlaywrightError:
                    continue
    except Exception as exc:  # belt-and-suspenders: one bad site must never break the batch
        logger.warning("Browser scrape failed for %s: %s", target, exc)
    finally:
        await page.close()

    if not pages_html:
        return {}

    result = aggregate_contacts(pages_html, website=target, country_code=country_code)
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


async def extract_contact_details(
    urls: list[str], country_code: Optional[str] = None
) -> list[dict]:
    """Batch-scrapes multiple websites with real headless-browser rendering --
    catches JS-injected contact info and dynamic footers a plain HTTP GET
    never sees. Uses ONE shared browser instance for the whole batch (launching
    a browser per URL would be far too resource-heavy) with concurrency capped
    across pages/tabs."""
    if not urls:
        return []

    results: list[dict] = [{}] * len(urls)
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_PAGES)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                context = await browser.new_context(user_agent=USER_AGENT, viewport={"width": 1280, "height": 800})

                async def _bounded(i: int, url: str) -> None:
                    async with semaphore:
                        results[i] = await _scrape_one(context, url, country_code)

                await asyncio.gather(*(_bounded(i, url) for i, url in enumerate(urls)))
            finally:
                await browser.close()
    except Exception as exc:  # e.g. browser binary missing/failed to launch
        logger.warning("Browser scraper batch failed: %s", exc)
        return [{} for _ in urls]

    return results


async def extract_contact_from_website(url: str, country_code: Optional[str] = None) -> dict:
    """Single-URL convenience wrapper for callers enriching one existing lead
    at a time (rather than a fresh batch of discovery results)."""
    results = await extract_contact_details([url], country_code=country_code)
    return results[0] if results else {}
