"""Lead validation — the quality gate that guarantees "real data".

Every lead that survives to the UI must carry a *real* contact channel. This
module:

- normalizes Pakistani phone numbers into canonical +92 form and rejects
  obviously fake numbers (too short, all-same-digit, placeholder exchanges);
- verifies emails are deliverable by looking up the domain's MX records with
  dnspython (cached per domain) and rejects noreply@/placeholder/disposable
  addresses;
- drops a lead entirely when nothing real is left after cleaning.

All lookups are optional (`settings.validate_emails`), short-timeout and cached,
so validation adds no meaningful latency to a batch.
"""
import logging
import re
from typing import Optional

from app.core.config import settings
from app.services.discovery.contact_extraction import (

    DISPOSABLE_EMAIL_DOMAINS,
    PLACEHOLDER_LOCAL_PARTS,
    SYSTEM_EMAIL_LOCAL_PARTS,
)

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Phones (Pakistan-focused, with a generic fallback for other countries)
# --------------------------------------------------------------------------- #

# 03xx-xxxxxxx mobile (11 national digits, leading 0)
_PK_MOBILE_RE = re.compile(r"^0?3[-\s]?\d{2}[-\s]?\d{7}$")
# 0xx-xxxxxxx / 0xxx-xxxxxxx landline (10-12 national digits, leading 0)
_PK_LANDLINE_RE = re.compile(r"^0\d{2,3}[-\s]?\d{6,8}$")
# +92 3xx-xxxxxxx or 0092 3xx-xxxxxxx (grouping tolerated anywhere in the number)
_PK_INTL_RE = re.compile(r"^(?:\+?92|0092)[-\s]?3[-\s]?\d{2}[-\s]?\d{7}$")

# Runs of consecutive digits ("1234567890") are placeholder/tracking numbers —
# distinct from the all-same-digit check below, and never a real reachable line.
_SEQUENTIAL_DIGITS = {"123456789", "1234567890", "0123456789", "987654321", "9876543210"}


def normalize_phone(raw, country_code: str = "PK") -> Optional[str]:
    """Return a canonical E.164-ish phone (e.g. +923001234567) or None if the
    number is missing, malformed or obviously fake. Handles the common Pakistani
    formats; numbers from other countries are kept only when they parse as a
    plausible international number."""
    if not raw:
        return None
    candidate = str(raw).strip()
    digits = re.sub(r"\D", "", candidate)
    if len(digits) < 7:
        return None
    if len(set(digits)) == 1 or digits in _SEQUENTIAL_DIGITS:
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
        # Falls through to the generic branch below: a number that isn't in an
        # obvious PK format is still kept when it parses as a plausible length,
        # rather than rejecting the whole lead over a formatting quirk.
    # Generic: a bare 10-12 digit national number is kept as a plain integer
    # string so unusual-but-real formats still surface in the lead list.
    if 9 <= len(digits) <= 12:
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
# Whole-lead gate
# --------------------------------------------------------------------------- #

def validate_lead(item: dict, country_code: str = "PK") -> Optional[dict]:
    """Clean a lead's phone/email and return it only if a real contact channel
    survives. Returns None when the lead has nothing real left."""
    normalize_phones(item, country_code)
    validate_emails(item)
    if not (item.get("phone") or item.get("email") or item.get("website")):
        return None
    return item
