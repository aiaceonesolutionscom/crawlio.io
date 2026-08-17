"""Google Maps lead crawler — the primary source of real local-business leads.

This is the same approach Apify's flagship "Google Maps Scraper" actor uses, and
it is why their data is good while the old web-search pipeline returned garbage:
instead of guessing business names and contacts out of search-result snippets, we
read the real place records Google Maps publishes — name, rating, review count,
category, full street address, phone, website, opening hours, plus code and the
exact lat/lon.

Design rules:
- Free and open-source: no API key. Requires Playwright's chromium binary
  (`playwright install chromium`) which is already a project dependency.
- Never raises: every failure path returns [] so the orchestrator can fall back
  to Overpass + directories. A block trips a circuit breaker and cooldown.
- Stealth-friendly: realistic UA/locale, randomized human-like delays, optional
  `PROXY_URL` for users who need to avoid bot detection at scale.
- ToS note: scraping Google Maps is against Google's Terms of Service. This is an
  informed, documented decision by the project owner, kept to modest request
  volumes (it is also exactly what Apify's actor does).
"""
import asyncio
import logging
import random
import re
from typing import Optional
from urllib.parse import quote

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright

from app.core.config import settings
from app.services.crawlers.base import CircuitBreaker, ProxyRotator, source_tracker, source_tracker

logger = logging.getLogger(__name__)

NAV_TIMEOUT_MS = 10_000
FEED_WAIT_MS = 6_000
SETTLE_MS = 700
# How many times we scroll the result feed before giving up on loading more.
MAX_SCROLLS = 24
# Concurrent place-page visits — bounded so a large request (e.g. 50 leads)
# finishes in reasonable wall-clock time without firing every navigation at
# once. Same total request volume as doing it sequentially, just parallelized
# within one browser context (the same technique Apify's own actor uses).
_PLACE_CONCURRENCY = 6
# Chromium build name for error diagnostics.
_CHROMIUM_HINT = "run `playwright install chromium`"

# A pool of realistic desktop Chrome user agents, rotated per crawl session so
# Google's fingerprint scoring sees a varied client identity rather than one
# fixed UA hammering from many IPs.
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36 Edg/124.0",
]
# Locales that match a session's proxy country when the pool is geo-targeted;
# keep en-PK as the conservative default so behavior stays predictable.
_LOCALES = ["en-PK", "en-US", "en-GB"]

# Google Maps blocks automation aggressively and a block tends to outlast a short
# cooldown, so the cooldown is long and the failure threshold low.
_breaker = CircuitBreaker(name="google-maps", failure_threshold=2, cooldown_seconds=600.0)
# Residential proxy pool — Google Maps is the one source that needs real
# residential IPs to stay unblocked at volume; empty pool = direct connection.
_proxy_rotator = ProxyRotator(settings.residential_proxy_list, name="google-maps-proxy")


# Signatures that mean "we are blocked", not "there are no results". Detected on
# the page/URL before we conclude the feed is empty, so we rotate + cooldown
# instead of mis-reporting a block as a zero-result search.
_CAPTCHA_MARKERS = (
    "unusual traffic",
    "our systems have detected",
    "recaptcha",
    "g-recaptcha",
    "captcha",
    "enable javascript and cookies to continue",
    "not a robot",
    "/sorry/",
)


def _looks_blocked(page_url: str, html_sample: str) -> bool:
    haystack = f"{page_url or ''} {html_sample or ''}".lower()
    return any(marker in haystack for marker in _CAPTCHA_MARKERS)


def _pick_user_agent() -> str:
    return random.choice(USER_AGENTS)


def _pick_locale() -> str:
    return random.choice(_LOCALES)


# Timezone that matches the session locale so the browser fingerprint is
# internally consistent (Google scores mismatched locale/timezone signals).
_TIMEZONES_BY_LOCALE = {
    "en-PK": "Asia/Karachi",
    "en-US": "America/New_York",
    "en-GB": "Europe/London",
}


def _pick_timezone(locale: str) -> str:
    return _TIMEZONES_BY_LOCALE.get(locale, "Asia/Karachi")


def _query_url(niche: str, city: str, country: str) -> str:
    query = quote(f"{niche} in {city}, {country}".strip().rstrip(","))
    return f"https://www.google.com/maps/search/{query}?hl=en"


async def _human_pause(low: float = 0.4, high: float = 1.4) -> None:
    await asyncio.sleep(random.uniform(low, high))


# Google encodes the coordinate pair of every place in its /place/ URL as
# ...!8m2!3d24.8607!4d67.0011 — this is the same source of truth the site's own
# embed uses, and far more reliable than parsing the rendered text.
_COORDS_RE = re.compile(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)")
# A rating appears in the card as a text node like "4.5" or "(123)".
_RATING_RE = re.compile(r"(\d(?:\.\d)?)")
_REVIEWS_RE = re.compile(r"\(([\d,]+)\)")


def _coords_from_url(url: str) -> tuple[Optional[float], Optional[float]]:
    match = _COORDS_RE.search(url or "")
    if not match:
        return None, None
    try:
        return float(match.group(1)), float(match.group(2))
    except ValueError:
        return None, None


async def _card_text(el) -> str:
    try:
        return (await el.inner_text()).strip()
    except PlaywrightError:
        return ""


def _parse_card(text: str) -> dict:
    """Pull name/rating/reviews out of a result card's inner text. Text looks
    roughly like:  \"Sakura Dental Studio\n4.5\n(120)\nDentist ...\" """
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    if not lines:
        return {}
    name = lines[0]
    rating: Optional[float] = None
    reviews: Optional[int] = None
    category: Optional[str] = None
    for i, line in enumerate(lines[1:], start=1):
        if rating is None and _RATING_RE.fullmatch(line):
            try:
                rating = float(line)
            except ValueError:
                rating = None
            continue
        if reviews is None and _REVIEWS_RE.fullmatch(line):
            try:
                reviews = int(re.sub(r"[^\d]", "", line))
            except ValueError:
                reviews = None
            continue
        if category is None and 2 <= len(line) <= 40:
            category = line
            break
    return {"name": name, "rating": rating, "review_count": reviews, "category": category}


async def _collect_feed_links(page, limit: int) -> list[dict]:
    """Scroll the result feed until we've collected `limit` unique place links
    (or hit MAX_SCROLLS). Returns [{name, rating, review_count, category, url,
    lat, lon}]."""
    links: list[dict] = []
    seen_urls: set[str] = set()

    async def _scan() -> None:
        anchors = await page.query_selector_all('div[role="feed"] a[href*="/maps/place/"]')
        for a in anchors:
            try:
                href = await a.get_attribute("href")
            except PlaywrightError:
                continue
            if not href or href in seen_urls:
                continue
            text = await _card_text(a)
            if not text:
                continue
            card = _parse_card(text)
            lat, lon = _coords_from_url(href)
            seen_urls.add(href)
            links.append({
                "name": card.get("name") or "",
                "rating": card.get("rating"),
                "review_count": card.get("review_count"),
                "category": card.get("category"),
                "url": href,
                "lat": lat,
                "lon": lon,
            })
            if len(links) >= limit:
                return

    feed = await page.query_selector('div[role="feed"]')
    if feed is None:
        return []

    await _scan()
    for _ in range(MAX_SCROLLS):
        if len(links) >= limit:
            break
        before = len(links)
        try:
            await feed.evaluate("(el) => el.scrollBy(0, el.scrollHeight)")
        except PlaywrightError:
            break
        await page.wait_for_timeout(random.randint(700, 1400))
        await _scan()
        # Nothing new loaded — the feed is exhausted.
        if len(links) == before:
            break

    return links[:limit]


async def _extract_panel(page, known_name: str) -> dict:
    """Read phone/address/website/hours/plus-code/rating/reviews out of a place's
    info panel. Every selector is wrapped so a missing/renamed element just
    yields fewer fields instead of failing the whole lead."""
    details: dict = {}

    try:
        h1 = await page.query_selector('[role="main"] h1')
        if h1:
            name = (await h1.inner_text()).strip()
            if name:
                details["name"] = name
    except PlaywrightError:
        pass

    # Rating + reviews: the star block has aria-label like "Rated 4.5 out of 5",
    # with the numeric value in a span[aria-hidden] and reviews as "(123)".
    for sel in ('div[aria-label*="out of 5"]', '[role="main"] [aria-label*="stars"]'):
        try:
            el = await page.query_selector(sel)
            if el:
                label = await el.get_attribute("aria-label")
                if label:
                    m = _RATING_RE.search(label)
                    if m:
                        details["rating"] = float(m.group(1))
                break
        except PlaywrightError:
            continue
    try:
        rev_el = await page.query_selector('button[aria-label*="reviews"]')
        if rev_el:
            label = await rev_el.get_attribute("aria-label") or ""
            m = re.search(r"([\d,]+)", label)
            if m:
                details["review_count"] = int(re.sub(r"[^\d]", "", m.group(1)))
    except PlaywrightError:
        pass

    # Category sits in the header as a button with jsaction="pane.rating.category".
    try:
        cat_el = await page.query_selector('button[jsaction*="category"] span, [role="main"] [data-attrid=""]')
        if cat_el:
            text = (await cat_el.inner_text()).strip()
            if text and 2 <= len(text) <= 40:
                details["category"] = text
    except PlaywrightError:
        pass

    # Phone.
    try:
        phone_el = await page.query_selector('button[data-item-id^="phone:"]')
        if phone_el:
            aria = await phone_el.get_attribute("aria-label")
            if aria and ":" in aria:
                details["phone"] = aria.split(":", 1)[-1].strip()
    except PlaywrightError:
        pass

    # Website.
    try:
        web_el = await page.query_selector('a[data-item-id="authority"]')
        if web_el:
            href = await web_el.get_attribute("href")
            if href:
                details["website"] = href
    except PlaywrightError:
        pass

    # Full street address.
    try:
        addr_el = await page.query_selector('button[data-item-id="address"]')
        if addr_el:
            aria = await addr_el.get_attribute("aria-label")
            if aria and ":" in aria:
                details["address"] = aria.split(":", 1)[-1].strip()
    except PlaywrightError:
        pass

    # Plus code.
    try:
        plus_el = await page.query_selector('button[data-item-id="oloc"]')
        if plus_el:
            aria = await plus_el.get_attribute("aria-label")
            if aria and ":" in aria:
                details["plus_code"] = aria.split(":", 1)[-1].strip()
    except PlaywrightError:
        pass

    # Opening hours: the compact row ("Open · Closes 8 PM") is the most stable
    # text surface; the full daily schedule needs a click we deliberately skip.
    try:
        oh_el = await page.query_selector('[data-item-id="oh"]')
        if oh_el:
            text = (await oh_el.inner_text()).strip().replace("\n", " · ")
            if text:
                details["hours"] = text
    except PlaywrightError:
        pass

    if not details.get("name") and known_name:
        details["name"] = known_name
    return details


async def _scrape_place(context, card: dict) -> dict:
    """Navigate directly to one place page and read its full info panel. Returns
    the merged card + panel record; never raises."""
    url = card.get("url")
    if not url:
        return dict(card)
    page = None
    try:
        page = await context.new_page()
        await page.goto(url, timeout=NAV_TIMEOUT_MS, wait_until="domcontentloaded")
        await page.wait_for_timeout(SETTLE_MS)
        panel = await _extract_panel(page, known_name=card.get("name") or "")
    except PlaywrightError as exc:
        logger.warning("Google Maps place scrape failed for %s: %s", url, exc)
        return dict(card)
    finally:
        if page is not None:
            try:
                await page.close()
            except PlaywrightError:
                pass

    record = {**card, **panel}
    if record.get("name"):
        record["name"] = record["name"]
    return record


async def search_businesses(niche: str, city: str, country: str, limit: int = 50) -> list[dict]:
    """Search Google Maps for a niche in a city and return real place records.

    Returns [] on any failure/block (never raises) so the orchestrator can fall
    back to other free sources.
    """
    if _breaker.open:
        logger.warning("Google Maps circuit open — skipping crawl")
        return []
    limit = max(1, min(limit, settings.google_maps_max_results))
    url = _query_url(niche, city, country)
    records: list[dict] = []

    # Pick a residential proxy for this crawl session (sticky across the whole
    # crawl so Google doesn't see mid-session IP churn); None = direct.
    proxy = await _proxy_rotator.get(sticky_key=f"maps:{niche}:{city}")
    user_agent = _pick_user_agent()
    locale = _pick_locale()

    try:
        async with async_playwright() as p:
            kwargs = {"headless": settings.google_maps_headless}
            if proxy:
                kwargs["proxy"] = {"server": proxy}
            try:
                browser = await p.chromium.launch(**kwargs)
            except PlaywrightError as exc:
                logger.warning("Google Maps crawler could not launch chromium: %s (%s)", exc, _CHROMIUM_HINT)
                return []
            try:
                context = await browser.new_context(
                    user_agent=user_agent,
                    locale=locale,
                    viewport={"width": 1280, "height": 900},
                    timezone_id=_pick_timezone(locale),
                )
                # Bandwidth optimization: block images/fonts/media/styles so the
                # heavy Maps page loads much faster and consumes far less proxy
                # bandwidth — we only need the DOM text, never the pixels.
                try:
                    await context.route(
                        "**/*",
                        lambda route: (
                            route.abort()
                            if route.request.resource_type in {"image", "font", "media", "stylesheet"}
                            else route.continue_()
                        ),
                    )
                except (PlaywrightError, AttributeError):
                    pass
                try:
                    page = await context.new_page()
                    try:
                        await page.goto(url, timeout=NAV_TIMEOUT_MS, wait_until="domcontentloaded")
                        # Google may show a consent/captcha wall — wait for the
                        # result feed to actually render before deciding.
                        await page.wait_for_selector('div[role="feed"]', timeout=FEED_WAIT_MS)
                    except PlaywrightError as exc:
                        # Distinguish a genuine block (captcha/unusual-traffic)
                        # from a normal zero-result search so we rotate + back
                        # off instead of silently reporting "no results".
                        try:
                            html_sample = await page.content()
                        except PlaywrightError:
                            html_sample = ""
                        if _looks_blocked(page.url, html_sample):
                            logger.warning(
                                "Google Maps appears blocked for %s in %s (proxy=%s): %s",
                                niche, city, proxy, exc,
                            )
                            _breaker.record_failure()
                            source_tracker.record_failure("google_maps")
                            _proxy_rotator.mark_failure(proxy)
                            return []
                        logger.warning("Google Maps feed not found for %s in %s: %s", niche, city, exc)
                        return []

                    feed = await _collect_feed_links(page, limit)
                    if not feed:
                        try:
                            html_sample = await page.content()
                        except PlaywrightError:
                            html_sample = ""
                        if _looks_blocked(page.url, html_sample):
                            logger.warning(
                                "Google Maps returned a block wall for %s in %s (proxy=%s)",
                                niche, city, proxy,
                            )
                            _breaker.record_failure()
                            source_tracker.record_failure("google_maps")
                            _proxy_rotator.mark_failure(proxy)
                            return []
                        logger.info("Google Maps found no results for %s in %s", niche, city)
                        return []

                    # Panel details per place, bounded by the requested limit.
                    panel_limit = max(1, min(len(feed), settings.google_maps_search_limit, limit))
                    semaphore = asyncio.Semaphore(_PLACE_CONCURRENCY)

                    async def _scrape_one(card: dict) -> Optional[dict]:
                        async with semaphore:
                            await _human_pause(0.6, 1.8)
                            record = await _scrape_place(context, card)
                            if record.get("name"):
                                record.setdefault("source", "google_maps")
                                return record
                            return None

                    scraped = await asyncio.gather(*(_scrape_one(card) for card in feed[:panel_limit]))
                    records = [r for r in scraped if r is not None]
                finally:
                    await page.close()
            finally:
                await browser.close()
    except PlaywrightError as exc:
        logger.warning("Google Maps crawler failed for %s in %s: %s", niche, city, exc)
        _breaker.record_failure()
        source_tracker.record_failure("google_maps")
        return []
    except Exception as exc:
        logger.warning("Google Maps crawler failed unexpectedly for %s in %s: %s", niche, city, exc)
        _breaker.record_failure()
        source_tracker.record_failure("google_maps")
        return []

    _breaker.record_success()
    source_tracker.record_success("google_maps")
    _proxy_rotator.mark_success(proxy)
    logger.info("Google Maps crawl for %s in %s returned %d records", niche, city, len(records))
    return records
