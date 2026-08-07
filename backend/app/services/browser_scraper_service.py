import asyncio
import logging
from urllib.parse import urljoin

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright

from app.services.contact_extraction import (
    extract_mailto,
    extract_tel,
    find_social_links,
    first_valid_email,
    first_valid_phone,
)

logger = logging.getLogger(__name__)

# Checked in order per site, stopping as soon as email+phone+socials are all
# found. Same ordering as the plain-HTTP scraper (website_scraper_service) —
# a contact/about page is far more likely to list an email than the homepage.
CONTACT_PATHS = ["", "/contact", "/contact-us", "/contact.html", "/about", "/about-us"]
NAV_TIMEOUT_MS = 12_000
# Real-browser navigation can still be mid-render right after "domcontentloaded"
# fires (JS-injected footers, cookie-consent-gated content) — a short settle
# window catches most of that without waiting for full network idle, which
# some sites (ad trackers, chat widgets) never actually reach.
SETTLE_MS = 400
# Each concurrent scrape holds open a browser page/tab; unbounded concurrency
# against a large batch would spike memory and can trip site-side rate limits.
MAX_CONCURRENT_PAGES = 6
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def _extract(html: str) -> dict:
    return {
        "email": extract_mailto(html) or first_valid_email(html),
        "phone": extract_tel(html) or first_valid_phone(html),
        "social_links": find_social_links(html),
    }


async def _scrape_one(context, url: str) -> dict:
    target = url if url.startswith(("http://", "https://")) else f"https://{url}"
    # A URL handed in here (e.g. from Tavily's website lookup) can already be a
    # specific subpage like ".../contact" rather than the bare domain — using
    # urljoin (like website_scraper_service does) means an absolute CONTACT_PATHS
    # entry replaces that page's path instead of being appended onto it, which
    # naive string concatenation would turn into a nonsense ".../contact/contact".
    found: dict = {}
    social_links: dict[str, str] = {}
    page = await context.new_page()
    try:
        for i, path in enumerate(CONTACT_PATHS):
            if found.get("email") and found.get("phone") and social_links:
                break
            try:
                await page.goto(urljoin(target, path), timeout=NAV_TIMEOUT_MS, wait_until="domcontentloaded")
            except PlaywrightError:
                if i == 0:
                    # Homepage itself didn't load — site is down or blocking us;
                    # further subpaths would just repeat the same timeout.
                    break
                continue
            await page.wait_for_timeout(SETTLE_MS)
            try:
                html = await page.content()
            except PlaywrightError:
                continue

            sub_found = _extract(html)
            found["email"] = found.get("email") or sub_found.get("email")
            found["phone"] = found.get("phone") or sub_found.get("phone")
            for platform, link in sub_found.get("social_links", {}).items():
                social_links.setdefault(platform, link)
    except Exception as exc:  # belt-and-suspenders: one bad site must never break the batch
        logger.warning("Browser scrape failed for %s: %s", target, exc)
    finally:
        await page.close()

    return {
        "email": found.get("email"),
        "phone": found.get("phone"),
        "social_links": social_links,
    }


async def extract_contact_details(urls: list[str]) -> list[dict]:
    """Batch-scrapes multiple websites with real headless-browser rendering —
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
                        results[i] = await _scrape_one(context, url)

                await asyncio.gather(*(_bounded(i, url) for i, url in enumerate(urls)))
            finally:
                await browser.close()
    except Exception as exc:  # e.g. browser binary missing/failed to launch
        logger.warning("Browser scraper batch failed: %s", exc)
        return [{} for _ in urls]

    return results


async def extract_contact_from_website(url: str) -> dict:
    """Single-URL convenience wrapper for callers enriching one existing lead
    at a time (rather than a fresh batch of discovery results)."""
    results = await extract_contact_details([url])
    return results[0] if results else {}
