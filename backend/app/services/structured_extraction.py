"""Structured-data extraction (JSON-LD / microdata) shared by both scrapers.

Many business sites publish their real contact details in a JSON-LD block
(Organization/LocalBusiness) even when they're hidden from the visible text by
templates or JS. These are the single most trustworthy contact source a page can
carry, so we parse them before falling back to loose regex on raw text.
"""
import json
import re
from typing import Optional
from urllib.parse import urlparse

JSONLD_RE = re.compile(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.IGNORECASE | re.DOTALL)

_SOCIAL_DOMAINS = {
    "facebook.com": "facebook",
    "instagram.com": "instagram",
    "linkedin.com": "linkedin",
    "twitter.com": "twitter",
    "x.com": "twitter",
    "youtube.com": "youtube",
    "tiktok.com": "tiktok",
}


def _social_platform_for_url(url: str) -> Optional[str]:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    for domain, platform in _SOCIAL_DOMAINS.items():
        if host == domain or host.endswith("." + domain):
            return platform
    return None


def _walk(obj, key: str, found: list):
    if isinstance(obj, dict):
        if key in obj and isinstance(obj[key], str) and obj[key].strip():
            found.append(obj[key].strip())
        for value in obj.values():
            _walk(value, key, found)
    elif isinstance(obj, list):
        for value in obj:
            _walk(value, key, found)


def extract_from_jsonld(html: str) -> dict:
    """Pull contact/profile fields out of every JSON-LD block on the page.
    Returns only what was actually present, never fabricated."""
    result: dict = {}

    def _first(*keys):
        found: list[str] = []
        for key in keys:
            _walk(ld, key, found)
            if found:
                break
        return found[0] if found else None

    for match in JSONLD_RE.findall(html or ""):
        try:
            raw = json.loads(match)
        except (json.JSONDecodeError, ValueError):
            continue
        nodes = raw if isinstance(raw, list) else [raw]
        for ld in nodes:
            if not isinstance(ld, dict):
                continue
            typ = ld.get("@type")
            types = typ if isinstance(typ, list) else [typ] if typ else []
            is_business = any(
                str(t).lower() in {"organization", "localbusiness", "restaurant", "store",
                                   "dentist", "clinic", "hotel", "salon", "gym", "pharmacy"}
                for t in types
            ) if types else False
            if not is_business and not any(t in types for t in ("Organization", "LocalBusiness")):
                pass

            email = _first("email")
            if email and not result.get("email"):
                result["email"] = email
            phone = _first("telephone", "phone")
            if phone and not result.get("phone"):
                result["phone"] = phone

            address = ld.get("address")
            if isinstance(address, dict):
                street = ", ".join(
                    p for p in [address.get("streetAddress"), address.get("addressLocality"),
                                address.get("postalCode")] if p
                )
                if street and not result.get("address"):
                    result["address"] = street
            elif isinstance(address, str) and address.strip() and not result.get("address"):
                result["address"] = address.strip()

            hours = ld.get("openingHours")
            if isinstance(hours, str) and hours and not result.get("hours"):
                result["hours"] = hours

            same_as = ld.get("sameAs")
            socials: dict[str, str] = {}
            if isinstance(same_as, str):
                same_as = [same_as]
            if isinstance(same_as, list):
                for url in same_as:
                    if not isinstance(url, str):
                        continue
                    platform = _social_platform_for_url(url)
                    if platform:
                        socials[platform] = url
            if socials:
                result["social_links"] = {**socials, **result.get("social_links", {})}

            website = ld.get("url")
            if isinstance(website, str) and website.startswith(("http://", "https://")) and not result.get("website"):
                result["website"] = website

    return result


_META_DESC_RE = re.compile(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)["\']', re.IGNORECASE)
_OG_DESC_RE = re.compile(r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']*)["\']', re.IGNORECASE)


def extract_meta_description(html: str) -> Optional[str]:
    match = _META_DESC_RE.search(html or "")
    if not match:
        match = _OG_DESC_RE.search(html or "")
    if not match:
        return None
    description = match.group(1).strip()
    return description[:280] or None
