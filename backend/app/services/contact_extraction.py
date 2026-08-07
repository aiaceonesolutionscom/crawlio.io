"""Shared regex helpers for pulling email/phone/website out of free text or HTML,
used by both the website-content scraper (all tiers) and Tavily enrichment (Pro+)."""
import re
from typing import Optional
from urllib.parse import unquote, urlparse

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(?:\+\d{1,3}[\s-]?)?(?:\(?\d{2,4}\)?[\s-]?){2,4}\d{3,4}")
MAILTO_RE = re.compile(r'mailto:([^"\'?\s]+)', re.IGNORECASE)
TEL_RE = re.compile(r'tel:([^"\'\s]+)', re.IGNORECASE)

SOCIAL_LINK_PATTERNS: dict[str, re.Pattern] = {
    "facebook": re.compile(r'https?://(?:www\.)?facebook\.com/[^\s"\'<>]+', re.IGNORECASE),
    "instagram": re.compile(r'https?://(?:www\.)?instagram\.com/[^\s"\'<>]+', re.IGNORECASE),
    "linkedin": re.compile(r'https?://(?:www\.)?linkedin\.com/[^\s"\'<>]+', re.IGNORECASE),
    "twitter": re.compile(r'https?://(?:www\.)?(?:twitter|x)\.com/[^\s"\'<>]+', re.IGNORECASE),
}

# Addresses/numbers that show up in scraped pages but aren't real business
# contacts (tracking pixels, platform boilerplate, placeholder examples).
EMAIL_BLOCKLIST_DOMAINS = {"sentry.io", "example.com", "wixpress.com", "godaddy.com", "schema.org"}
# A rendered page's HTML (especially a JS-heavy single-page app scraped with a
# real browser) is full of asset references shaped like "name@2x-hash.png" —
# these match EMAIL_RE's loose pattern but are image/script filenames, not
# addresses. Real email TLDs never end in one of these.
NON_EMAIL_TLDS = {
    "png", "jpg", "jpeg", "gif", "svg", "webp", "ico", "css", "js", "json",
    "woff", "woff2", "ttf", "map", "mp4", "webm",
}
NON_WEBSITE_DOMAINS = {
    "facebook.com", "instagram.com", "linkedin.com", "twitter.com", "x.com",
    "yelp.com", "tripadvisor.com", "maps.google.com", "goo.gl", "youtube.com",
    "wikipedia.org", "foursquare.com", "justdial.com", "yellowpages.com",
    "waze.com", "maps.apple.com", "bing.com", "openstreetmap.org",
}


def _is_valid_email(candidate: str) -> bool:
    if not candidate or "@" not in candidate:
        return False
    domain = candidate.split("@")[-1].lower()
    tld = domain.rsplit(".", 1)[-1] if "." in domain else ""
    return domain not in EMAIL_BLOCKLIST_DOMAINS and tld not in NON_EMAIL_TLDS


def _is_valid_phone_digits(candidate: str) -> bool:
    digits = re.sub(r"\D", "", candidate)
    return 7 <= len(digits) <= 15


def first_valid_email(text: str) -> Optional[str]:
    for match in EMAIL_RE.findall(text or ""):
        if _is_valid_email(match):
            return match
    return None


def first_valid_phone(text: str) -> Optional[str]:
    for match in PHONE_RE.findall(text or ""):
        if not _is_valid_phone_digits(match):
            continue
        digits = re.sub(r"\D", "", match)
        # A bare unformatted digit run (no +, space, dash, parens, dot) found
        # loose in page text is far more often a timestamp, order ID, or
        # tracking hash than a real phone number — genuine displayed numbers
        # are almost always formatted with some separator.
        if match == digits:
            continue
        return match.strip()
    return None


def extract_mailto(html: str) -> Optional[str]:
    """Pull the first email out of a mailto: link, if it's actually valid —
    an explicit mailto: is a stronger signal than a loose text match, but its
    href value still isn't guaranteed to be real (template placeholders,
    tracking links)."""
    match = MAILTO_RE.search(html or "")
    if not match:
        return None
    candidate = unquote(match.group(1)).split("?")[0]
    return candidate if _is_valid_email(candidate) else None


def extract_tel(html: str) -> Optional[str]:
    """Pull the first phone number out of a tel: link, if it's actually valid.
    Unlike first_valid_phone, a tel: href is legitimately allowed to be a bare
    digit run (that's the normal format for tel: links) — only the digit-count
    check applies here, not the "must be formatted" heuristic."""
    match = TEL_RE.search(html or "")
    if not match:
        return None
    candidate = unquote(match.group(1))
    return candidate if _is_valid_phone_digits(candidate) else None


def is_own_website(url: str) -> bool:
    if not url:
        return False
    host = urlparse(url).netloc.lower().removeprefix("www.")
    return bool(host) and not any(host == d or host.endswith("." + d) for d in NON_WEBSITE_DOMAINS)


def find_social_links(html: str) -> dict[str, str]:
    links: dict[str, str] = {}
    for platform, pattern in SOCIAL_LINK_PATTERNS.items():
        match = pattern.search(html or "")
        if match:
            # Trim trailing HTML-ish junk a greedy match can pick up (quotes are
            # excluded by the pattern already, but stray punctuation isn't).
            links[platform] = match.group(0).rstrip(').,;')
    return links
