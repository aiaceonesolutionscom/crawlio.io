"""Free business-directory crawlers (Pakistan focus).

Directories are the tertiary source behind Google Maps and OSM/Overpass: they
add businesses Google Maps might miss, and — unlike OSM — occasionally carry a
real email or social profile. This module hits the plain-HTML pages of free
directories (YellowPages.pk, Cybo) with httpx, parses listings heuristically and
returns only records that carry at least one real contact channel (phone, email
or website).

Everything degrades to [] on failure (bot-wall, 404, markup change) so a broken
directory can never block a search. All requests go through a shared rate limiter
to stay a good citizen of these free sites.
"""
import logging
import re
from typing import Optional
from urllib.parse import quote, urljoin, urlparse

import httpx

from app.core.config import settings
from app.services.discovery.crawlers.base import CircuitBreaker, RateLimiter

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
_limiter = RateLimiter(name="directories", interval=0.7)

_TEL_RE = re.compile(r'href=["\']tel:([^"\'?]+)', re.IGNORECASE)
_MAILTO_RE = re.compile(r'href=["\']mailto:([^"\'?]+)', re.IGNORECASE)
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_HEADING_RE = re.compile(
    r"<h([1-4])[^>]*>\s*(.*?)\s*</h\1>|<a[^>]+class=\"[^\"]*(?:name|title|heading)[^\"]*\"[^>]*>\s*(.*?)\s*</a>",
    re.IGNORECASE | re.DOTALL,
)
# A generous window of markup before a tel:/mailto: link — the business name
# heading normally sits right above the contact row in a listing card.
_CONTEXT_BEFORE = 700

_CLEAN_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _clean(text: str) -> str:
    text = _CLEAN_TAG_RE.sub(" ", text or "")
    return _WS_RE.sub(" ", text).strip()


def _is_external(href: str, page_host: str) -> bool:
    try:
        host = urlparse(urljoin(page_host, href)).netloc.lower()
    except ValueError:
        return False
    return bool(host) and host != page_host and not host.endswith("." + page_host)


async def _fetch(url: str) -> Optional[str]:
    """GET a directory page. Returns HTML or None; never raises."""
    if _breaker.open:
        return None
    await _limiter.wait()
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, headers=HEADERS, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code >= 400:
                logger.info("Directory page %s returned %d", url, resp.status_code)
                return None
            return resp.text
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Directory fetch failed for %s: %s", url, exc)
        _breaker.record_failure()
        return None


_BLOCK_OPEN_RE = re.compile(r"<(li|article|tr)\b[^>]*>", re.IGNORECASE)
_BLOCK_CLOSE_RE = re.compile(r"</(li|article|tr)>", re.IGNORECASE)


def _split_blocks(html: str) -> list[str]:
    """Split directory markup into listing blocks using <li>/<article>/<tr>
    containers (the containers directory sites actually use). Nested containers
    are ignored — close enough for typical listing markup."""
    blocks: list[str] = []
    for m in _BLOCK_OPEN_RE.finditer(html):
        close = _BLOCK_CLOSE_RE.search(html, m.end())
        block_end = close.start() if close else len(html)
        blocks.append(html[m.start():block_end])
    return blocks


def _parse_block(block: str, page_host: str) -> Optional[dict]:
    """Extract one business from a listing block. Requires a tel: link (that's
    what makes it a reachable lead) plus whatever name/email/website the same
    block carries — never borrows fields from an adjacent listing."""
    tel_m = _TEL_RE.search(block)
    if not tel_m:
        return None
    raw_phone = tel_m.group(1).strip()
    if len(re.sub(r"\D", "", raw_phone)) < 7:
        return None

    name = ""
    for heading_match in _HEADING_RE.finditer(block):
        candidate = _clean(heading_match.group(2) or heading_match.group(3) or "")
        if candidate:
            name = candidate
    if not name:
        return None

    email = None
    mailto = _MAILTO_RE.search(block)
    if mailto:
        email = mailto.group(1).strip().lower()
    if not email:
        text_email = _EMAIL_RE.findall(block)
        email = text_email[0].lower() if text_email else None

    website = None
    for wm in re.finditer(r'href=["\'](https?://[^"\']+)["\']', block, re.IGNORECASE):
        href = wm.group(1)
        if _is_external(href, page_host):
            website = href
            break

    return {"name": name, "phone": raw_phone, "email": email, "website": website}


def _parse_listings(html: str, base_url: str) -> list[dict]:
    """Parse a directory page into business records. When the page uses
    <li>/<article>/<tr> listing containers we parse each block independently;
    otherwise we fall back to a window around each tel: link (still bounded, so
    a neighbour's email can't leak in). Works across directories regardless of
    their exact CSS classes."""
    if not html:
        return []
    page_host = urlparse(base_url).netloc.lower()
    blocks = _split_blocks(html)
    if not blocks:
        blocks = [html]

    seen: set[tuple] = set()
    out: list[dict] = []

    for block in blocks:
        if _TEL_RE.search(block) is None:
            # Unsplit page fallback: process each tel link's local window.
            if len(blocks) == 1:
                for m in _TEL_RE.finditer(block):
                    window = html[max(0, m.start() - _CONTEXT_BEFORE):min(len(html), m.end() + 400)]
                    record = _parse_block(window, page_host)
                    if record:
                        key = (record["name"].lower(), record["phone"])
                        if key not in seen:
                            seen.add(key)
                            out.append(record)
                return out
            continue
        record = _parse_block(block, page_host)
        if not record:
            continue
        key = (record["name"].lower(), record["phone"])
        if key in seen:
            continue
        seen.add(key)
        out.append(record)

    return out


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").strip().lower()).strip("-")


async def _yellowpages_pk(niche: str, city: str, country: str, limit: int) -> list[dict]:
    base = "https://www.yellowpages.com.pk"
    url = f"{base}/search/{quote(_slug(niche))}/{quote(_slug(city))}"
    html = await _fetch(url)
    if not html:
        # Fallback: category browse page for the city.
        url = f"{base}/browse/{quote(_slug(city))}"
        html = await _fetch(url)
    records = _parse_listings(html or "", url)
    return records[:limit]


async def _cybo(niche: str, city: str, country: str, limit: int) -> list[dict]:
    base = "https://www.cybo.com"
    # Cybo's global search is the most stable surface and is city-aware.
    url = f"{base}/search/?q={quote(f'{niche} {city} {country}')}&lang=en"
    html = await _fetch(url)
    records = _parse_listings(html or "", url)
    if len(records) < limit:
        # Per-city directory page sometimes lists more.
        city_url = f"{base}/PK/{quote(_slug(city))}/{quote(_slug(niche))}/"
        city_html = await _fetch(city_url)
        if city_html:
            city_records = _parse_listings(city_html, city_url)
            seen = {r["phone"] for r in records}
            for r in city_records:
                if r["phone"] not in seen:
                    seen.add(r["phone"])
                    records.append(r)
    return records[:limit]


async def search_businesses(niche: str, city: str, country: str, limit: int = 50) -> list[dict]:
    """Query every enabled directory and merge unique records. Never raises —
    returns whatever the sources that responded produced."""
    if not settings.directory_enabled:
        return []
    limit = max(1, min(limit, 100))

    sources = [_yellowpages_pk, _cybo]
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
    return records
