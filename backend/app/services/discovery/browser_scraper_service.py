import asyncio
import logging
import random
import re
from typing import Optional
from urllib.parse import urljoin

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright

from app.services.discovery.scrape_utils import aggregate_contacts, discover_contact_urls, normalize_website_url
from app.services.discovery.website_scraper_service import fetch_plain


logger = logging.getLogger(__name__)

NAV_TIMEOUT_MS = 30_000
SETTLE_MS = 3500
MAX_CONCURRENT_PAGES = 10
MAX_PAGES_PER_SITE = 10

# Rotating user agents to avoid detection
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

# Common WAF/Access Denied indicators
WAF_PATTERNS = [
    re.compile(r"access denied", re.I),
    re.compile(r"blocked by", re.I),
    re.compile(r"please enable javascript", re.I),
    re.compile(r"checking your browser", re.I),
    re.compile(r"ray id:", re.I),
    re.compile(r"cf-ray", re.I),
    re.compile(r"akamai", re.I),
    re.compile(r"cloudflare", re.I),
    re.compile(r"reference #\d+", re.I),
    re.compile(r"captcha", re.I),
    re.compile(r"you don't have permission", re.I),
    re.compile(r"forbidden", re.I),
    re.compile(r"403 forbidden", re.I),
    re.compile(r"attention required", re.I),
    re.compile(r"sucuri", re.I),
    re.compile(r"wordfence", re.I),
    re.compile(r"incapsula", re.I),
]

# Known good contact page paths to try first
CONTACT_PATHS_PRIORITY = [
    "/contact", "/contact-us", "/contact.html", "/contact.php",
    "/about", "/about-us", "/about.html",
    "/get-in-touch", "/reach-us", "/connect",
    "/info", "/information",
]


def _is_waf_page(html: str) -> Optional[str]:
    """Detect if page is a WAF/block page. Returns reason if detected, else None."""
    if not html:
        return "empty_response"
    text = html.lower()
    for pattern in WAF_PATTERNS:
        if pattern.search(text):
            return "waf_blocked"
    # Check for extremely minimal content (likely a block page)
    if len(text.strip()) < 500 and ("script" not in text or "challenge" in text):
        return "minimal_content"
    return None


def _get_random_user_agent() -> str:
    """Return a random user agent from the pool."""
    return random.choice(USER_AGENTS)


async def _try_http_fallback(url: str, country_code: Optional[str]) -> dict:
    """Fallback to plain HTTP scraping when browser fails."""
    try:
        result = await fetch_plain(url, country_code, max_pages=MAX_PAGES_PER_SITE)
        if result:
            result["_scraped_ok"] = True
            result["_scrape_error"] = None
            result["_fallback"] = "http"
            return result
    except Exception as exc:
        logger.debug("HTTP fallback failed for %s: %s", url, exc)
    return {"_scraped_ok": False, "_scrape_error": "http_fallback_failed", "_fallback": "http"}


async def _try_textise_fallback(url: str, country_code: Optional[str]) -> dict:
    """Last-resort fallback: use textise dot iitty style extraction via textise dot iitty API or similar.
    For now, this tries to fetch via textise dot iitty-like service."""
    # This would integrate with a service like textise dot iitty, but for now
    # we'll just return a failed result since we don't have an external service configured.
    return {"_scraped_ok": False, "_scrape_error": "textise_not_configured", "_fallback": "textise"}


async def _scrape_one(context, url: str, country_code: Optional[str]) -> dict:
    """Navigate a single business site: homepage, then discovered contact
    subpages, and aggregate ranked contacts across whatever loaded.
    Returns a dict with scraped fields plus optional '_scrape_error' key
    if the site was unreachable/blocked, and '_scraped_ok' boolean.
    
    Implements multi-tier fallback:
    1. Primary: Full browser render with JS execution
    2. Fallback 1: Retry with different UA and longer waits
    3. Fallback 2: Plain HTTP scraping (no JS)
    4. Fallback 3: Textise-style extraction (if configured)"""
    target = url.strip()
    if not target.startswith(("http://", "https://")):
        target = f"https://{target}"
    if not target:
        return {"_scraped_ok": False, "_scrape_error": "invalid_url"}

    # Try primary scrape with retries
    for attempt in range(3):
        pages_html: list[str] = []
        home_loaded = False
        scrape_error: Optional[str] = None
        
        # Rotate user agent on retry
        if attempt > 0:
            await context.set_extra_http_headers({"User-Agent": _get_random_user_agent()})
        
        page = await context.new_page()
        try:
            # First try with 'load' (wait for all resources); on timeout fallback to 'domcontentloaded'
            try:
                response = await page.goto(target, timeout=NAV_TIMEOUT_MS, wait_until="load")
            except PlaywrightError:
                response = await page.goto(target, timeout=NAV_TIMEOUT_MS, wait_until="domcontentloaded")
            
            # Check for redirect to http (common with some CDN configs)
            final_url = page.url
            if final_url.startswith("http://") and target.startswith("https://"):
                logger.warning("Redirected from HTTPS to HTTP for %s, staying on HTTPS", target)
                await page.goto(target, timeout=NAV_TIMEOUT_MS, wait_until="domcontentloaded")
            
            # Wait for network to settle
            try:
                await page.wait_for_load_state("networkidle", timeout=15000)
            except PlaywrightError:
                pass
            
            # Handle common cookie banners
            try:
                for btn_text in ["Accept", "Accept All", "I Agree", "Allow All", "Agree", "OK", "Got it", "Accept Cookies", "Allow", "Consent"]:
                    btn = page.locator(f'button:has-text("{btn_text}"), a:has-text("{btn_text}"), [role="button"]:has-text("{btn_text}")').first
                    if await btn.is_visible(timeout=1000):
                        await btn.click()
                        await page.wait_for_timeout(500)
                        break
            except PlaywrightError:
                pass
            
            # Wait for potential challenges to solve
            challenge_wait = 8000 + (attempt * 3000)  # Increase wait on retries
            await page.wait_for_timeout(challenge_wait)
            
            # Check after challenge wait
            html_after_wait = await page.content()
            waf_after = _is_waf_page(html_after_wait)
            if waf_after:
                # Try additional wait for challenge resolution
                await page.wait_for_timeout(5000 + (attempt * 2000))
                home_html = await page.content()
                waf_after2 = _is_waf_page(home_html)
                if not waf_after2:
                    pages_html.append(home_html)
                    home_loaded = True
                else:
                    scrape_error = f"waf_blocked: homepage (persisted after challenge wait, attempt {attempt + 1})"
                    home_loaded = False
            else:
                # Initial settle for JS to execute
                await page.wait_for_timeout(SETTLE_MS)
                
                # Human-like mouse movement
                try:
                    await page.mouse.move(100, 100)
                    await page.wait_for_timeout(200)
                    await page.mouse.move(500, 300)
                    await page.wait_for_timeout(200)
                except PlaywrightError:
                    pass
                
                # Scroll to trigger lazy-loaded content
                try:
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await page.wait_for_timeout(1500)
                    await page.evaluate("window.scrollTo(0, 0)")
                    await page.wait_for_timeout(500)
                except PlaywrightError:
                    pass
                
                home_html = await page.content()
                pages_html.append(home_html)
                home_loaded = True

            if home_loaded:
                # Check if homepage is WAF-blocked
                waf_reason = _is_waf_page(pages_html[0])
                if waf_reason:
                    scrape_error = f"waf_blocked: homepage"
                    home_loaded = False
                
                if home_loaded:
                    # Discover contact subpages
                    sub_urls = discover_contact_urls(target, pages_html[0], max_urls=MAX_PAGES_PER_SITE)
                    
                    # Prioritize known contact paths
                    prioritized_urls = []
                    for path in CONTACT_PATHS_PRIORITY:
                        full_url = urljoin(target, path)
                        if full_url not in prioritized_urls:
                            prioritized_urls.append(full_url)
                    for sub_url in sub_urls:
                        if sub_url not in prioritized_urls:
                            prioritized_urls.append(sub_url)
                    
                    for sub_url in prioritized_urls[:MAX_PAGES_PER_SITE]:
                        try:
                            await page.goto(sub_url, timeout=NAV_TIMEOUT_MS, wait_until="domcontentloaded")
                            await page.wait_for_timeout(SETTLE_MS)
                            
                            # Scroll subpage
                            try:
                                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                                await page.wait_for_timeout(500)
                            except PlaywrightError:
                                pass
                            
                            html = await page.content()
                            if html and html not in pages_html:
                                sub_waf = _is_waf_page(html)
                                if not sub_waf:
                                    pages_html.append(html)
                                else:
                                    logger.debug("Subpage %s WAF-blocked: %s", sub_url, sub_waf)
                        except PlaywrightError:
                            continue
            
            # If we got content, break out of retry loop
            if pages_html:
                break
                
        except Exception as exc:
            scrape_error = f"unexpected_error: {exc}"
            logger.warning("Browser scrape attempt %d failed for %s: %s", attempt + 1, target, exc)
        finally:
            await page.close()
        
        # If we got content, break
        if pages_html:
            break
        
        # Wait before retry
        if attempt < 2:
            await asyncio.sleep(2 + attempt)
    
    # If all browser attempts failed, try HTTP fallback
    if not pages_html:
        logger.info("Browser scrape failed for %s after 3 attempts, trying HTTP fallback", target)
        http_result = await _try_http_fallback(target, country_code)
        if http_result.get("_scraped_ok"):
            return http_result
        
        # Last resort: textise fallback (if configured)
        logger.info("HTTP fallback failed for %s, trying textise fallback", target)
        textise_result = await _try_textise_fallback(target, country_code)
        if textise_result.get("_scraped_ok"):
            return textise_result
        
        return {
            "_scraped_ok": False,
            "_scrape_error": scrape_error or "all_fallbacks_failed",
            "website": target,
            "_fallback_attempts": ["browser", "http", "textise"],
        }

    base_result = {
        "_scraped_ok": scrape_error is None and len(pages_html) > 0,
        "_scrape_error": scrape_error,
        "website": target,
    }

    if not pages_html:
        return base_result

    result = aggregate_contacts(pages_html, website=target, country_code=country_code)
    base_result.update({
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
    })
    return base_result


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
            browser = await p.chromium.launch(headless=True, args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-site-isolation-trials",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-extensions",
                "--disable-default-apps",
                "--disable-popup-blocking",
            ])
            try:
                # Use random user agent for each batch
                ua = _get_random_user_agent()
                context = await browser.new_context(
                    user_agent=ua,
                    viewport={"width": 1280, "height": 800},
                    locale="en-US",
                    timezone_id="America/New_York",
                    permissions=["geolocation"],
                    device_scale_factor=1,
                    is_mobile=False,
                    has_touch=False,
                    java_script_enabled=True,
                    bypass_csp=True,
                    ignore_https_errors=True,
                )
                # Anti-detection: hide webdriver property
                await context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    window.chrome = {runtime: {}};
                    Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                    Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
                    // Override permissions
                    const originalQuery = window.navigator.permissions.query;
                    window.navigator.permissions.query = (parameters) => (
                        parameters.name === 'notifications' ?
                            Promise.resolve({ state: Notification.permission }) :
                            originalQuery(parameters)
                    );
                """)
                # Block some tracking scripts to avoid detection
                await context.route("**/*", lambda route: route.abort() if any(domain in route.request.url for domain in ["doubleclick.net", "googletagmanager.com", "google-analytics.com", "facebook.net", "googlesyndication.com", "analytics.google.com"]) else route.continue_())

                async def _bounded(i: int, url: str) -> None:
                    async with semaphore:
                        results[i] = await _scrape_one(context, url, country_code)

                # A single stalled site (never-ending stream, hung connection
                # that ignores timeouts) must not hold the whole batch hostage.
                # 8 min is generous enough for every site to finish while still
                # bounding the worst case; per-page NAV_TIMEOUT does the fine
                # grained control.
                await asyncio.wait_for(
                    asyncio.gather(*(_bounded(i, url) for i, url in enumerate(urls))),
                    timeout=480.0,
                )
            finally:
                await browser.close()
    except asyncio.TimeoutError:
        logger.warning("Browser scraper batch hit overall timeout (%d urls)", len(urls))
    except Exception as exc:  # e.g. browser binary missing/failed to launch
        logger.warning("Browser scraper batch failed: %s", exc)
        return [{} for _ in urls]

    return results


async def extract_contact_from_website(url: str, country_code: Optional[str] = None) -> dict:
    """Single-URL convenience wrapper for callers enriching one existing lead
    at a time (rather than a fresh batch of discovery results)."""
    results = await extract_contact_details([url], country_code=country_code)
    return results[0] if results else {}
