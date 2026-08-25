"""Lead validation — the quality gate that guarantees "real data".

Every lead that survives to the UI must carry a *real* contact channel. This
module:

- normalizes phone numbers into canonical E.164 form and rejects
  obviously fake numbers (too short, all-same-digit, placeholder exchanges);
- verifies emails are deliverable by looking up the domain's MX records with
  dnspython (cached per domain) and rejects noreply@/placeholder/disposable
  addresses;
- validates website URLs are real business sites (not directories/social);
- validates address has minimum viable components;
- validates category is present and meaningful;
- drops a lead entirely when nothing real is left after cleaning.

All lookups are optional (`settings.validate_emails`), short-timeout and cached,
so validation adds no meaningful latency to a batch.
"""
import logging
import re
from typing import Optional
from urllib.parse import urlparse

from app.core.config import settings
from app.services.discovery.contact_extraction import (
    DISPOSABLE_EMAIL_DOMAINS,
    PLACEHOLDER_LOCAL_PARTS,
    SYSTEM_EMAIL_LOCAL_PARTS,
    NON_WEBSITE_DOMAINS,
    DIRECTORY_DOMAINS,
    DIRECTORY_MARKERS,
)

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Phones (worldwide E.164 normalization)
# --------------------------------------------------------------------------- #

# 03xx-xxxxxxx mobile (11 national digits, leading 0)
_PK_MOBILE_RE = re.compile(r"^0?3[-\s]?\d{2}[-\s]?\d{7}$")
# 0xx-xxxxxxx / 0xxx-xxxxxxx landline (10-12 national digits, leading 0)
_PK_LANDLINE_RE = re.compile(r"^0\d{2,3}[-\s]?\d{6,8}$")
# +92 3xx-xxxxxxx or 0092 3xx-xxxxxxx (grouping tolerated anywhere in the number)
_PK_INTL_RE = re.compile(r"^(?:\+?92|0092)[-\s]?3[-\s]?\d{2}[-\s]?\d{7}$")

# Generic international phone pattern
_INT_PHONE_RE = re.compile(r"^\+?\d{1,3}[\s-]?\d{4,14}$")


def normalize_phone(raw, country_code: str = "PK") -> Optional[str]:
    """Return a canonical E.164 phone (e.g. +923001234567) or None if the
    number is missing, malformed or obviously fake. Handles common Pakistani
    formats; numbers from other countries use the worldwide calling-code map
    to return canonical E.164 (+1...+44...+971...+91...)."""
    if not raw:
        return None
    candidate = str(raw).strip()
    digits = re.sub(r"\D", "", candidate)
    if len(digits) < 7:
        return None
    if len(set(digits)) == 1 or digits in {"1234567", "12345678", "123456789", "0123456789"}:
        return None
    if candidate.startswith("+") and len(digits) >= 11:
        return "+" + digits

    cc = str(country_code or "PK").upper()
    if cc == "PK":
        if _PK_MOBILE_RE.match(candidate):
            return "+92" + digits[-10:]
        if _PK_INTL_RE.match(candidate):
            return "+92" + digits[-10:]
        if _PK_LANDLINE_RE.match(candidate):
            return "+92" + digits[-10:]
        return None
    # Other countries: normalize using the worldwide calling-code map
    from app.services.discovery.crawlers.whatsapp_links import normalize_e164

    e164 = normalize_e164(candidate, cc)
    if e164:
        return e164
    # Fallback: keep plausible national number
    if 9 <= len(digits) <= 15:
        return digits
    return None


def normalize_phones(item: dict, country_code: str = "PK") -> None:
    """In-place: replace `item["phone"]` with the normalized form, or drop it."""
    raw = item.get("phone")
    normalized = normalize_phone(raw, country_code)
    if normalized:
        item["phone"] = normalized
    else:
        item["phone"] = None


# --------------------------------------------------------------------------- #
# Emails (format + MX verification)
# --------------------------------------------------------------------------- #

_MX_CACHE: dict[str, Optional[bool]] = {}


def _has_mx(domain: str) -> bool:
    """True when the domain advertises MX records (i.e. it can receive mail).
    Cached per domain; a DNS error is treated as False so bad domains drop."""
    key = domain.lower()
    if key in _MX_CACHE:
        return bool(_MX_CACHE[key])
    result = False
    try:
        import dns.resolver

        resolver = dns.resolver.Resolver()
        resolver.timeout = 2.0
        resolver.lifetime = 3.0
        answers = resolver.resolve(key, "MX")
        result = bool(answers) and len(answers) > 0
    except Exception:
        result = False
    _MX_CACHE[key] = result
    return result


def _is_placeholder_email(local: str) -> bool:
    return bool(PLACEHOLDER_LOCAL_PARTS.search(local))


def validate_email(email: str) -> Optional[str]:
    """Return the cleaned email if it's plausibly real and deliverable, else
    None. Rejects system/placeholder/disposable addresses and, when MX checks
    are enabled, domains that can't receive mail."""
    if not email:
        return None
    cleaned = str(email).strip().lower()
    if "@" not in cleaned or "." not in cleaned.split("@")[-1]:
        return None
    local, domain = cleaned.split("@", 1)
    if not local or len(local) > 64 or len(domain) > 255:
        return None
    if local in SYSTEM_EMAIL_LOCAL_PARTS or local.startswith(("noreply", "no-reply", "donotreply", "mailer", "postmaster", "webmaster", "abuse")):
        return None
    if _is_placeholder_email(local):
        return None
    if domain in DISPOSABLE_EMAIL_DOMAINS:
        return None
    if settings.validate_emails and not _has_mx(domain):
        return None
    return cleaned


def validate_emails(item: dict) -> None:
    """In-place: keep `item["email"]` only if it validates."""
    email = validate_email(item.get("email"))
    item["email"] = email


# --------------------------------------------------------------------------- #
# Website validation
# --------------------------------------------------------------------------- #

def validate_website(url: str) -> Optional[str]:
    """Validate and normalize a website URL. Returns None for directory/social
    links, or URLs that aren't real business websites."""
    if not url:
        return None
    normalized = str(url).strip()
    if not normalized.startswith(("http://", "https://")):
        normalized = "https://" + normalized
    try:
        parsed = urlparse(normalized)
        host = parsed.netloc.lower().removeprefix("www.")
        if not host:
            return None
        # Reject directory/social/non-business domains
        if any(host == d or host.endswith("." + d) for d in NON_WEBSITE_DOMAINS):
            return None
        if any(host == d or host.endswith("." + d) for d in DIRECTORY_DOMAINS):
            return None
        if any(marker in host for marker in DIRECTORY_MARKERS):
            return None
        # Reject auto-generated preview/deploy hosts
        preview_hosts = {"netlify.app", "vercel.app", "github.io", "gitlab.io", 
                        "surge.sh", "pages.dev", "firebaseapp.com", "webflow.io", 
                        "wixsite.com", "wixpress.com"}
        if any(host == p or host.endswith("." + p) for p in preview_hosts):
            return None
        return normalized
    except Exception:
        return None


def validate_website_field(item: dict) -> None:
    """In-place: keep `item["website"]` only if it validates."""
    website = validate_website(item.get("website"))
    item["website"] = website


# --------------------------------------------------------------------------- #
# Address validation
# --------------------------------------------------------------------------- #

def validate_address(address: str) -> Optional[str]:
    """Validate address has minimum viable components (street + city at minimum)."""
    if not address:
        return None
    cleaned = str(address).strip()
    # Must have at least some alphanumeric content
    if not re.search(r"[a-zA-Z0-9]", cleaned):
        return None
    # Reject obviously fake/placeholder addresses
    fake_patterns = [
        r"^\d+$",  # Just numbers
        r"^test", r"^sample", r"^example", r"^dummy", r"^placeholder",
        r"^n/?a$", r"^unknown$", r"^not\s+provided$",
    ]
    for pattern in fake_patterns:
        if re.search(pattern, cleaned, re.IGNORECASE):
            return None
    # Must have reasonable length
    if len(cleaned) < 5:
        return None
    return cleaned


def validate_address_field(item: dict) -> None:
    """In-place: keep `item["address"]` only if it validates."""
    address = validate_address(item.get("address"))
    item["address"] = address


# --------------------------------------------------------------------------- #
# Category validation
# --------------------------------------------------------------------------- #

def validate_category(category: str) -> Optional[str]:
    """Validate category is meaningful and not a placeholder."""
    if not category:
        return None
    cleaned = str(category).strip()
    # Reject placeholder categories
    fake_patterns = [
        r"^test", r"^sample", r"^example", r"^dummy", r"^placeholder",
        r"^n/?a$", r"^unknown$", r"^not\s+provided$", r"^category$",
    ]
    for pattern in fake_patterns:
        if re.search(pattern, cleaned, re.IGNORECASE):
            return None
    if len(cleaned) < 2:
        return None
    return cleaned


def validate_category_field(item: dict) -> None:
    """In-place: keep `item["category"]` only if it validates."""
    category = validate_category(item.get("category") or item.get("industry"))
    item["category"] = category
    if category:
        item["industry"] = category


# --------------------------------------------------------------------------- #
# Name validation
# --------------------------------------------------------------------------- #

def validate_name(name: str) -> Optional[str]:
    """Validate business name is meaningful."""
    if not name:
        return None
    cleaned = str(name).strip()
    # Remove keyword stuffing (pipe-separated SEO spam)
    cleaned = cleaned.split("|", 1)[0].strip()
    # Reject obviously fake names
    fake_patterns = [
        r"^test", r"^sample", r"^example", r"^dummy", r"^placeholder",
        r"^n/?a$", r"^unknown$", r"^not\s+provided$",
        r"^\d+$",  # Just numbers
    ]
    for pattern in fake_patterns:
        if re.search(pattern, cleaned, re.IGNORECASE):
            return None
    if len(cleaned) < 2:
        return None
    return cleaned


def validate_name_field(item: dict) -> None:
    """In-place: keep `item["name"]` only if it validates."""
    name = validate_name(item.get("name"))
    item["name"] = name


# --------------------------------------------------------------------------- #
# Whole-lead gate
# --------------------------------------------------------------------------- #

def validate_lead(item: dict, country_code: str = "PK") -> Optional[dict]:
    """Clean a lead's fields and return it only if a real contact channel
    survives. Returns None when the lead has nothing real left.

    Accepted contact channels (at least ONE required):
    - phone (normalized to E.164 when plausible),
    - email (MX-verified when validation is enabled),
    - website (valid business website, not directory/social),
    - name + street address + lat/lon (a real, geocoded business from OSM/BizData
      that simply publishes no phone/email/website — visitable, not invented).
    A bare name with no channel is still dropped.
    
    Also validates: name, category/industry, address."""
    # Validate all fields
    validate_name_field(item)
    normalize_phones(item, country_code)
    validate_emails(item)
    validate_website_field(item)
    validate_address_field(item)
    validate_category_field(item)

    # Check if name survived validation
    if not item.get("name"):
        return None

    has_phone = bool(item.get("phone"))
    has_email = bool(item.get("email"))
    has_website = bool(item.get("website"))

    if has_phone or has_email or has_website:
        return item

    # OSM-derived sources (BizData, Overpass) sometimes carry a real street
    # address + coordinates but no phone/email/website. They're real, visitable
    # businesses — accept them with a lower completeness score rather than
    # dropping them, so thin niches still return what the free web actually has.
    name = (item.get("name") or "").strip()
    address = (item.get("address") or "").strip()
    lat, lon = item.get("lat"), item.get("lon")
    has_coords = isinstance(lat, (int, float)) and isinstance(lon, (int, float)) \
        and -90 <= lat <= 90 and -180 <= lon <= 180
    if name and address and has_coords:
        return item

    # No real contact channel at all - drop the lead
    return None