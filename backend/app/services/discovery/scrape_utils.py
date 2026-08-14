"""Shared web-scraping helpers used by both the plain-HTTP scraper (free tier)
and the headless-browser scraper (Pro+): discovering contact subpages and
aggregating ranked contact info across the pages that were actually fetched.
"""
import logging
import re
from typing import Optional
from urllib.parse import urljoin, urlparse

from app.services.discovery.contact_extraction import (

    best_email,
    best_phone,
    collect_emails,
    collect_phones,
    decode_cfemail,
    extract_mailto,
    extract_tel,
    find_social_links,
)
from app.services.discovery.structured_extraction import extract_from_jsonld, extract_meta_description


logger = logging.getLogger(__name__)

# Pages that genuinely carry contact info. A homepage rarely lists an email, but
# its links usually point at a page that does — so we first fetch the known
# conventional paths, then crawl homepage links that look like contact/about.
CONTACT_SUBPATHS = ["/contact", "/contact-us", "/contact.html", "/about", "/about-us"]

# Anchor text (or href) that signals a contact-ish page. Also accepts the
# Spanish/French/Arabic-adjacent spellings small businesses often use.
CONTACT_HINT_RE = re.compile(
    r"contact|get\s*[-_]?in\s*touch|getintouch|reach\s*us|connect\s*with|about\s*us|say\s*hello|تواصل",
    re.IGNORECASE,
)

_MAX_CONTACT_PAGES = 8


def normalize_website_url(url: str) -> str:
    """Return a canonical https://host[/path] for a user-provided or discovered
    website string, so dedup keys compare equal for "site.pk" vs "https://site.pk/."""
    if not url:
        return ""
    target = url.strip()
    if not target.startswith(("http://", "https://")):
        target = f"https://{target}"
    parsed = urlparse(target)
    host = (parsed.netloc or "").lower().removeprefix("www.")
    path = parsed.path or ""
    if path.endswith("/") and len(path) > 1:
        path = path.rstrip("/")
    if not host:
        return ""
    return f"https://{host}{path}"


def _extract_links(html: str) -> list[tuple[str, str]]:
    """(href, anchor_text) pairs from anchor tags. Anchor text is stripped of
    nested tags so "Contact &amp; Us" still matches the hint regex."""
    links: list[tuple[str, str]] = []
    for href, inner in re.findall(r'<a[^>]+href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>', html or "", re.IGNORECASE | re.DOTALL):
        text = re.sub(r"<[^>]+>", "", inner)
        text = re.sub(r"\s+", " ", text).strip()
        links.append((href, text))
    return links


def _same_origin(base_url: str, candidate: str) -> bool:
    try:
        base_host = urlparse(base_url).netloc.lower().removeprefix("www.")
        cand_host = urlparse(urljoin(base_url, candidate)).netloc.lower().removeprefix("www.")
    except ValueError:
        return False
    return bool(base_host) and bool(cand_host) and cand_host == base_host


def discover_contact_urls(homepage_url: str, homepage_html: str, max_urls: int = _MAX_CONTACT_PAGES) -> list[str]:
    """Find the pages most likely to hold contact info by crawling same-origin
    links from the homepage whose href/anchor text looks contact-ish. Returns
    absolute URLs, conventional paths first, then crawled matches in order."""
    discovered: list[str] = []
    seen: set[str] = set()

    def _add(url: str) -> None:
        absolute = urljoin(homepage_url, url) if not url.startswith(("http://", "https://")) else url
        try:
            parsed = urlparse(absolute)
        except ValueError:
            return
        if parsed.scheme not in ("http", "https"):
            return
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
        if normalized and normalized not in seen:
            seen.add(normalized)
            discovered.append(normalized)

    for subpath in CONTACT_SUBPATHS:
        _add(subpath)

    for href, text in _extract_links(homepage_html):
        if len(discovered) >= max_urls:
            break
        if not _same_origin(homepage_url, href):
            continue
        haystack = f"{href} {text}"
        if CONTACT_HINT_RE.search(haystack):
            _add(href)
    return discovered[:max_urls]


def aggregate_contacts(
    pages: list[str],
    website: str,
    country_code: Optional[str] = None,
) -> dict:
    """Turn the raw HTML of every page we fetched for one business into a single
    ranked contact profile. Emails/phones are ranked (domain-match to the site
    wins, boilerplate/system addresses lose), mailto/tel links are the strongest
    signal, JSON-LD fills in address/hours/website, and social links are merged
    across pages."""
    all_html = "\n".join(p for p in pages if p)

    emails = collect_emails(all_html)
    mailto_email = next((e for p in pages if (e := extract_mailto(p))), None)
    cf_email = next((e for p in pages if (e := decode_cfemail(p))), None)
    preferred_email = mailto_email or cf_email

    phones = collect_phones(all_html)
    tel_phone = None
    for page in pages:
        candidate = extract_tel(page)
        if candidate:
            tel_phone = candidate
            break

    social_links: dict[str, str] = {}
    for page in pages:
        for platform, link in find_social_links(page).items():
            social_links.setdefault(platform, link)

    structured: dict = {}
    for page in pages:
        page_structured = extract_from_jsonld(page)
        for key in ("email", "phone", "website", "address", "hours", "social_links"):
            if key in page_structured and not structured.get(key):
                structured[key] = page_structured[key]
        if page_structured.get("social_links"):
            structured["social_links"] = {**page_structured.get("social_links", {}), **structured.get("social_links", {})}

    email = best_email(all_html, website=website, preferred=preferred_email) or structured.get("email")
    phone = best_phone(all_html, country_code=country_code, preferred=tel_phone) or structured.get("phone")
    social_links = {**social_links, **structured.get("social_links", {})}

    description = extract_meta_description(all_html)

    return {
        "email": email,
        "phone": phone,
        "website": structured.get("website") or website,
        "address": structured.get("address"),
        "hours": structured.get("hours"),
        "description": description,
        "social_links": social_links,
        "email_candidates": emails,
        "phone_candidates": phones,
        "page_text": all_html[:24_000],
    }
