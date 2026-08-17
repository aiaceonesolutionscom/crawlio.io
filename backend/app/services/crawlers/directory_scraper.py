"""Free business-directory crawlers (worldwide focus).

Directories are the tertiary source behind Google Maps and OSM/Overpass: they
add businesses Google Maps might miss, and — unlike OSM — occasionally carry a
real email or social profile. This module hits the plain-HTML pages of free
directories that actually respond without a bot-wall (verified live:
YellowPage.pk for Pakistan, Hotfrog for the US/UK), parses listings
heuristically and returns only records that carry at least one real contact
channel (phone, email or website).

Everything degrades to [] on failure (bot-wall, 404, markup change) so a broken
directory can never block a search. All requests go through a shared rate limiter
to stay a good citizen of these free sites.
"""
import html
import json
import logging
import re
from typing import Optional
from urllib.parse import quote, urljoin, urlparse

from app.core.config import settings
from app.services.crawlers.base import CircuitBreaker, ProxyRotator, RateLimiter, RobotsTxt, fetch_text, source_tracker

logger = logging.getLogger(__name__)

TIMEOUT = 12.0
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
_breaker = CircuitBreaker(name="directories", failure_threshold=3, cooldown_seconds=300.0)
_limiter = RateLimiter(name="directories", interval=1.2)
_robots = RobotsTxt()
_proxy_rotator = ProxyRotator(settings.http_proxy_list, name="directory-proxy")

_TEL_RE = re.compile(r'href=["\']tel:([^"\'?]+)', re.IGNORECASE)
_MAILTO_RE = re.compile(r'href=["\']mailto:([^"\'?]+)', re.IGNORECASE)
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

_CLEAN_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _clean(text: str) -> str:
    text = _CLEAN_TAG_RE.sub(" ", text or "")
    return _WS_RE.sub(" ", text).strip()


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").strip().lower()).strip("-")


async def _fetch(url: str) -> Optional[str]:
    """GET a directory page with TLS impersonation. Returns HTML or None;
    never raises."""
    if _breaker.open:
        return None
    await _limiter.wait()
    proxy = await _proxy_rotator.get(sticky_key=urlparse(url).netloc)
    outcome = await fetch_text(
        url,
        headers=HEADERS,
        timeout=TIMEOUT,
        proxy=proxy,
    )
    if outcome.blocked:
        logger.warning("Directory %s served a block/rate-limit wall (%d)", url, outcome.status)
        _breaker.record_failure()
        source_tracker.record_failure("directory")
        _proxy_rotator.mark_failure(proxy)
        return None
    if not outcome.ok:
        logger.info("Directory page %s returned %d", url, outcome.status)
        return None
    _proxy_rotator.mark_success(proxy)
    return outcome.text


# ---------------------------------------------------------------------------
# YellowPage.pk — Pakistan. Real server-rendered listing cards:
# <div class="card listing-card"> containing an <h2><a>NAME</a>, a tel: link
# and an address span. No email/website on the card, so phone is the contact.
# ---------------------------------------------------------------------------

_YP_CARD_SPLIT_RE = re.compile(r'(?=<div class="card listing-card)')


def _parse_yellowpage_cards(html_text: str) -> list[dict]:
    out: list[dict] = []
    seen: set[tuple] = set()
    for card in _YP_CARD_SPLIT_RE.split(html_text or "")[1:]:
        tel = _TEL_RE.search(card)
        if not tel:
            continue
        phone = html.unescape(tel.group(1)).strip()
        if len(re.sub(r"\D", "", phone)) < 7:
            continue
        name = ""
        nm = re.search(r"<h2[^>]*>\s*<a[^>]*>(.*?)</a>", card, re.S) or re.search(r"<h2[^>]*>(.*?)</h2>", card, re.S)
        if nm:
            name = html.unescape(_clean(nm.group(1)))
        if not name:
            continue
        address = ""
        am = re.search(r'fa-map-marker-alt[^>]*>\s*</i>\s*<span[^>]*>(.*?)</span>', card, re.S)
        if am:
            address = html.unescape(_clean(am.group(1)))
        key = (name.lower(), phone)
        if key in seen:
            continue
        seen.add(key)
        out.append({"name": name, "phone": phone, "email": None, "website": None, "address": address})
    return out


async def _yellowpage_pk(niche: str, city: str, country: str, limit: int) -> list[dict]:
    base = "https://yellowpage.pk"
    url = f"{base}/search?skeywords={quote(niche)}"
    html_text = await _fetch(url)
    records = _parse_yellowpage_cards(html_text or "")
    if len(records) < limit and city and country:
        # City-scoped search when the generic one comes up short.
        url2 = f"{base}/search?skeywords={quote(niche)}&city={quote(city)}"
        html2 = await _fetch(url2)
        if html2:
            extra = _parse_yellowpage_cards(html2)
            seen = {(r["name"].lower(), r["phone"]) for r in records}
            for r in extra:
                if (r["name"].lower(), r["phone"]) not in seen:
                    seen.add((r["name"].lower(), r["phone"]))
                    records.append(r)
    return records[:limit]


# ---------------------------------------------------------------------------
# Hotfrog — global (US/UK/etc). Listing cards are plain <li> blocks, and the
# page embeds `window.mapBubbles = [...]` JSON with structured per-place
# {name, address, tel} payloads — both are parsed. Search URL shape:
# /search/{country}/{city}/{keyword} or /search/{country}/{keyword}.
# ---------------------------------------------------------------------------

_HP_CARD_SPLIT_RE = re.compile(r'(?=<li class="(?:py-3|.*?business))', re.IGNORECASE)


def _parse_hotfrog(html_text: str) -> list[dict]:
    out: list[dict] = []
    seen: set[tuple] = set()

    # Primary: the embedded mapBubbles JSON (clean, structured, includes tel).
    m = re.search(r"window\.mapBubbles=(\[.*?\]);", html_text or "", re.S)
    if m:
        try:
            for bubble in json.loads(m.group(1)):
                h = bubble.get("html", "")
                nm = re.search(r"<strong>(.*?)</strong>", h)
                tel = re.search(r'tel:([^"\'<]+)', h)
                if not nm or not tel:
                    continue
                name = html.unescape(_clean(nm.group(1)))
                phone = html.unescape(tel.group(1)).strip()
                if not name or len(re.sub(r"\D", "", phone)) < 7:
                    continue
                key = (name.lower(), phone)
                if key in seen:
                    continue
                seen.add(key)
                out.append({"name": name, "phone": phone, "email": None, "website": None})
        except (ValueError, TypeError):
            pass
    return out


async def _hotfrog(niche: str, city: str, country: str, limit: int) -> list[dict]:
    base = "https://www.hotfrog.com"
    cc = _country_code(country)
    cc_path = cc if cc else "us"
    city_slug = _slug(city)
    # /search/us/restaurants and /search/us/new-york/restaurants both work.
    url = f"{base}/search/{cc_path}/{quote(niche)}"
    html_text = await _fetch(url)
    records = _parse_hotfrog(html_text or "")
    if len(records) < limit and city_slug:
        url2 = f"{base}/search/{cc_path}/{city_slug}/{quote(niche)}"
        html2 = await _fetch(url2)
        if html2:
            extra = _parse_hotfrog(html2)
            seen = {(r["name"].lower(), r["phone"]) for r in records}
            for r in extra:
                if (r["name"].lower(), r["phone"]) not in seen:
                    seen.add((r["name"].lower(), r["phone"]))
                    records.append(r)
    return records[:limit]


def _country_code(country: str) -> str:
    """Best-effort ISO country code for Hotfrog's per-country path; defaults to
    the global .com surface when unknown."""
    lower = (country or "").lower()
    known = {
        "pakistan": "pk", "united states": "us", "usa": "us", "america": "us",
        "united kingdom": "uk", "britain": "uk", "england": "uk",
        "australia": "au", "canada": "ca", "new zealand": "nz",
        "united arab emirates": "ae", "uae": "ae", "saudi arabia": "sa",
        "india": "in", "germany": "de", "france": "fr", "spain": "es",
        "italy": "it", "netherlands": "nl", "singapore": "sg",
    }
    return known.get(lower, "")


async def search_businesses(niche: str, city: str, country: str, limit: int = 50) -> list[dict]:
    """Query every enabled directory and merge unique records. Never raises —
    returns whatever the sources that responded produced."""
    if not settings.directory_enabled:
        return []
    limit = max(1, min(limit, 100))

    sources = [
        _yellowpage_pk, _hotfrog,
    ]
    # Country-aware sourcing: YellowPage.pk only covers Pakistan; Hotfrog covers
    # the US/UK/etc. Run only the relevant ones so a Pakistan search isn't
    # flooded with Pakistan records for a US city (or vice versa).
    country_lower = (country or "").lower()
    if country_lower and "pakistan" not in country_lower and "pk" != country_lower.strip():
        sources = [_hotfrog]
    records: list[dict] = []
    by_phone: dict[str, dict] = {}

    def _add(record: dict) -> None:
        record.setdefault("source", "directory")
        record.setdefault("industry", niche.strip().title())
        record.setdefault("social_links", {})
        phone_key = re.sub(r"\D", "", record.get("phone") or "")
        if phone_key and phone_key in by_phone:
            # Same business seen by two directory sites — fill gaps instead of
            # dropping the richer record (e.g. one site has the email).
            existing = by_phone[phone_key]
            for key in ("email", "website", "address"):
                if not existing.get(key) and record.get(key):
                    existing[key] = record[key]
            return
        if phone_key:
            by_phone[phone_key] = record
        records.append(record)

    for source in sources:
        try:
            found = await source(niche, city, country, limit=limit)
        except Exception as exc:
            logger.warning("Directory source %s failed for %s in %s: %s", source.__name__, niche, city, exc)
            continue
        for record in found:
            _add(record)
            if len(records) >= limit:
                break
        if len(records) >= limit:
            break

    _breaker.record_success()
    source_tracker.record_success("directory")
    return records
