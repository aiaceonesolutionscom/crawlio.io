"""Shared regex helpers for pulling email/phone/website out of free text or HTML,
used by the website-content scraper (plain HTTP for all tiers, headless browser
for Pro+) and by the discovery crawlers' lead validation.

Picking the *right* contact out of a page matters as much as finding one: rendered
pages are full of boilerplate emails (theme authors, agency footers, "noreply"
system addresses) and stray formatted numbers (faxes, tracking IDs). Instead of
returning the first regex match, we collect every candidate, score it, and hand
back the most likely real business contact.
"""
import html as html_mod
import re
from typing import Optional
from urllib.parse import unquote, urlparse

from app.data.directory_domains import DIRECTORY_DOMAINS, DIRECTORY_MARKERS

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(?:\+\d{1,3}[\s-]?)?(?:\(?\d{2,4}\)?[\s-]?){2,4}\d{3,4}")
MAILTO_RE = re.compile(r'mailto:([^"\'?\s]+)', re.IGNORECASE)
TEL_RE = re.compile(r'tel:([^"\'\s]+)', re.IGNORECASE)
CFEMAIL_RE = re.compile(r'data-cfemail="([0-9a-fA-F]+)"')
# Cloudflare obfuscates emails as HTML entities in the DOM; also handle the plain
# &commat;/&#64; style entities some site builders emit.
ENTITY_AT_RE = re.compile(r"&#64;|&#x40;|&commat;")

SOCIAL_LINK_PATTERNS: dict[str, re.Pattern] = {
    "facebook": re.compile(r'https?://(?:www\.)?facebook\.com/[^\s"\'<>]+', re.IGNORECASE),
    "instagram": re.compile(r'https?://(?:www\.)?instagram\.com/[^\s"\'<>]+', re.IGNORECASE),
    "linkedin": re.compile(r'https?://(?:www\.)?linkedin\.com/[^\s"\'<>]+', re.IGNORECASE),
    "twitter": re.compile(r'https?://(?:www\.)?(?:twitter|x)\.com/[^\s"\'<>]+', re.IGNORECASE),
    "youtube": re.compile(r'https?://(?:www\.)?youtube\.com/@?[^\s"\'<>]+|https?://(?:www\.)?youtube\.com/c[^\s"\'<>]+', re.IGNORECASE),
    "tiktok": re.compile(r'https?://(?:www\.)?tiktok\.com/@[^\s"\'<>]+', re.IGNORECASE),
    "whatsapp": re.compile(r'https?://(?:www\.)?(?:wa\.me|api\.whatsapp\.com)/[^\s"\'<>]+', re.IGNORECASE),
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
    "about.me", "linktr.ee", "linkin.bio", "beacons.ai",
    # Auto-generated preview/deploy hosts — never a business's real site
    "netlify.app", "vercel.app", "github.io", "gitlab.io", "surge.sh",
    "pages.dev", "firebaseapp.com", "webflow.io", "wixsite.com",
}

# Throwaway inbox providers — an email on one of these is almost never a real
# business contact a sales team can reach.
DISPOSABLE_EMAIL_DOMAINS = {
    "mailinator.com", "yopmail.com", "guerrillamail.com", "sharklasers.com",
    "trashmail.com", "10minutemail.com", "temp-mail.org", "throwawaymail.com",
    "tempmail.com", "maildrop.cc", "getnada.com", "dispostable.com",
    "mytemp.email", "fakeinbox.com", "mailnesia.com", "spamgourmet.com",
    "tempinbox.com", "discard.email", "emailondeck.com",
}

# "System" local-parts that bounce or go to an inbox nobody reads — they exist
# on almost every site, so they're heavily penalized but not rejected outright
# (a site with only a noreply address is still better with a scored candidate
# than with nothing).
SYSTEM_EMAIL_LOCAL_PARTS = {
    "noreply", "no-reply", "no_reply", "donotreply", "do-not-reply", "mailer",
    "mailer-daemon", "postmaster", "webmaster", "abuse", "admin", "support-mail",
}
# Placeholder template emails site builders leave in ("yourname@yourdomain.com").
PLACEHOLDER_LOCAL_PARTS = re.compile(r"your|example|test|demo|sample|dummy|xxxx|yourdomain|email@", re.IGNORECASE)

# Trusted generic "contact desk" local parts — exactly the address a real
# business wants outreach sent to.
GOOD_GENERIC_LOCAL_PARTS = {
    "info", "contact", "hello", "hi", "sales", "bookings", "booking",
    "reservations", "reservation", "reception", "office", "admin", "manager",
}

# Phone length/dial-code sanity by country. `national` is the number of digits
# after the country code. Only used to *penalize* mismatches (a lead in PK with
# a +1 US-style number is suspicious), never to reject outright.
_COUNTRY_DIAL: dict[str, tuple[str, int]] = {
    "PK": ("+92", 10),
    "IN": ("+91", 10),
    "US": ("+1", 10),
    "GB": ("+44", 10),
    "CA": ("+1", 10),
    "AU": ("+61", 9),
    "AE": ("+971", 9),
    "SA": ("+966", 9),
    "QA": ("+974", 8),
    "BH": ("+973", 8),
    "KW": ("+965", 8),
    "OM": ("+968", 8),
    "TR": ("+90", 10),
    "DE": ("+49", 11),
    "FR": ("+33", 9),
    "ES": ("+34", 9),
    "IT": ("+39", 10),
    "NL": ("+31", 9),
    "SG": ("+65", 8),
    "HK": ("+852", 8),
    "MY": ("+60", 9),
    "BD": ("+880", 10),
    "NP": ("+977", 10),
    "LK": ("+94", 9),
}


def _decode_entities(text: str) -> str:
    """Decode HTML entities AND Cloudflare's &#64;-style obfuscation. Entity
    decoding alone leaves `a&#64;b.com` as `a@b.com` but CF turns the `@` into
    a hex character reference that html.unescape does NOT resolve, so do both."""
    if not text:
        return text
    decoded = ENTITY_AT_RE.sub("@", text)
    return html_mod.unescape(decoded)


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def _email_domain(email: str) -> str:
    return email.rsplit("@", 1)[-1].lower() if "@" in email else ""


def _is_valid_email(candidate: str) -> bool:
    if not candidate or "@" not in candidate:
        return False
    domain = candidate.split("@")[-1].lower()
    tld = domain.rsplit(".", 1)[-1] if "." in domain else ""
    return domain not in EMAIL_BLOCKLIST_DOMAINS and tld not in NON_EMAIL_TLDS


def _is_disposable_email(email: str) -> bool:
    # A blanket ".xyz" TLD reject used to live here, but that's a false-positive
    # risk: legitimate small-business domains increasingly use cheap gTLDs like
    # .xyz. Only the known throwaway-provider list counts as disposable now.
    domain = _email_domain(email)
    return domain in DISPOSABLE_EMAIL_DOMAINS


def _is_placeholder_email(email: str) -> bool:
    local = email.split("@", 1)[0].lower()
    return bool(PLACEHOLDER_LOCAL_PARTS.search(local))


def _domain_matches_website(email: str, website: Optional[str]) -> bool:
    if not website or "@" not in email:
        return False
    email_domain = _email_domain(email)
    if not email_domain:
        return False
    host = urlparse(website if website.startswith(("http://", "https://")) else f"http://{website}").netloc.lower()
    host = host.removeprefix("www.").split(":")[0]
    if not host or host in NON_WEBSITE_DOMAINS:
        return False
    return email_domain == host or email_domain.endswith("." + host) or host.endswith("." + email_domain)


def collect_emails(text: str, max_candidates: int = 40) -> list[str]:
    """All unique, plausibly-valid emails in a page, in order of appearance,
    with HTML-entity/Cloudflare obfuscation already decoded."""
    seen: set[str] = set()
    out: list[str] = []
    decoded = _decode_entities(text or "")
    for match in EMAIL_RE.findall(decoded):
        email = _normalize_email(match)
        if not _is_valid_email(email) or email in seen:
            continue
        seen.add(email)
        out.append(email)
        if len(out) >= max_candidates:
            break
    return out


def _email_score(email: str, website: Optional[str] = None) -> int:
    score = 0
    if _domain_matches_website(email, website):
        score += 40
    if _is_disposable_email(email):
        score -= 40
    if _is_placeholder_email(email):
        score -= 25
    local = email.split("@", 1)[0].lower()
    if local in SYSTEM_EMAIL_LOCAL_PARTS:
        score -= 30
    elif local in GOOD_GENERIC_LOCAL_PARTS:
        score += 10
    if email.endswith((".gov", ".edu")):
        score -= 5
    return score


def best_email(text: str, website: Optional[str] = None, preferred: Optional[str] = None) -> Optional[str]:
    """Return the single most likely *real* business email on a page. Unlike a
    naive first-match, this ranks candidates: an email whose domain matches the
    business's own website outranks a boilerplate "info@theme-author.com" that
    happens to appear earlier in the DOM. Returns None when nothing plausible
    survives filtering."""
    candidates = collect_emails(text)
    if not candidates:
        return None
    if preferred and _normalize_email(preferred) in candidates:
        return _normalize_email(preferred)

    def _sort_key(email: str):
        return _email_score(email, website)

    ranked = sorted(candidates, key=_sort_key, reverse=True)
    top = ranked[0]
    # A candidate that is both disposable AND placeholder is not worth saving.
    if _is_disposable_email(top) and _is_placeholder_email(top):
        return None
    return top


def first_valid_email(text: str) -> Optional[str]:
    """Backwards-compatible wrapper (no website signal): best-effort single
    email from loose text."""
    return best_email(text)


def _phone_digits(candidate: str) -> str:
    return re.sub(r"\D", "", candidate)


def _is_valid_phone_digits(candidate: str) -> bool:
    digits = _phone_digits(candidate)
    return 7 <= len(digits) <= 15


def _looks_fake_phone(digits: str) -> bool:
    """Patterns that are overwhelmingly not a real reachable number."""
    if not digits:
        return True
    if len(digits) < 7:
        return True
    if len(set(digits)) == 1:  # 1111111...
        return True
    if digits in {"1234567", "12345678", "123456789", "0123456789"}:
        return True
    if digits.startswith(("000", "111", "999")) and len(digits) >= 10:
        # 111/000/999-prefixed 10+ digit numbers are almost always fake.
        return True
    return False


def _phone_country_penalty(candidate: str, country_code: Optional[str]) -> int:
    """A country-aware sanity check: a lead in Pakistan whose number carries a
    US +1 dial code is suspect. Returns a penalty to deprioritize, never reject."""
    if not country_code:
        return 0
    entry = _COUNTRY_DIAL.get(str(country_code).upper())
    if not entry:
        return 0
    dial, national = entry
    digits = _phone_digits(candidate)
    if candidate.strip().startswith(dial) or digits.startswith(dial.lstrip("+")):
        remaining = len(digits) - len(dial.lstrip("+"))
        # Allow normal national-length variance (mobiles vs landlines differ).
        if remaining > 0 and not (national - 2 <= remaining <= national + 2):
            return -20
        return 5
    # No explicit dial code — treat as national number, penalize clearly-wrong lengths.
    if len(digits) == national + 2:  # e.g. 12 digits in a 10-digit country
        return -10
    return 0


_PHONE_CONTEXT_RE = re.compile(
    r"(?:tel|phone|call|contact|whatsapp|mobile|cell|hotline|helpline)\s*[:\-]?\s*$",
    re.IGNORECASE,
)
_PHONE_CONTEXT_WINDOW = 20


def collect_phones(text: str, max_candidates: int = 30) -> list[str]:
    """Unique phone candidates from a page, decoded, in order of appearance."""
    seen: set[str] = set()
    out: list[str] = []
    decoded = _decode_entities(text or "")
    for match in PHONE_RE.finditer(decoded):
        candidate = match.group(0).strip()
        if not _is_valid_phone_digits(candidate):
            continue
        digits = _phone_digits(candidate)
        if _looks_fake_phone(digits):
            continue
        # A bare unformatted digit run loose in page text is far more often a
        # timestamp/order-id/hash than a real number — UNLESS it's immediately
        # preceded by an explicit phone label ("Call: 03001234567" with no
        # space is a common compact-footer pattern), in which case the context
        # makes it trustworthy despite the missing formatting.
        if candidate == digits:
            window = decoded[max(0, match.start() - _PHONE_CONTEXT_WINDOW):match.start()]
            if not _PHONE_CONTEXT_RE.search(window):
                continue
        key = digits
        if key in seen:
            continue
        seen.add(key)
        out.append(candidate)
        if len(out) >= max_candidates:
            break
    return out


def _phone_score(candidate: str, country_code: Optional[str]) -> int:
    score = 0
    digits = _phone_digits(candidate)
    if candidate.strip().startswith("+") and digits:
        score += 5  # explicit international format is a strong signal
    elif candidate.strip().startswith(("0", "(")):
        score += 2  # conventional local formatting
    score += _phone_country_penalty(candidate, country_code)
    if candidate.strip().startswith("555-") or candidate.strip().endswith("-5555"):
        score -= 20  # classic placeholder-exchange numbers
    return score


def best_phone(text: str, country_code: Optional[str] = None, preferred: Optional[str] = None) -> Optional[str]:
    """Single best phone candidate from page text, ranked by international
    formatting and country-dial sanity. `preferred` is a tel: link value which
    is trusted to win ties."""
    candidates = collect_phones(text)
    if not candidates:
        return None
    if preferred:
        for c in candidates:
            if _phone_digits(c) == _phone_digits(preferred):
                return c

    ranked = sorted(candidates, key=lambda c: _phone_score(c, country_code), reverse=True)
    return ranked[0]


def first_valid_phone(text: str) -> Optional[str]:
    """Backwards-compatible wrapper (no country signal)."""
    return best_phone(text)


def decode_cfemail(html: str) -> list[str]:
    """Cloudflare email-protection encodes the address as a hex blob where every
    byte is XORed against the first byte. Returns any decoded addresses found."""
    emails: list[str] = []
    for match in CFEMAIL_RE.findall(html or ""):
        try:
            data = bytes.fromhex(match)
        except ValueError:
            continue
        if len(data) < 2:
            continue
        key = data[0]
        email = "".join(chr(b ^ key) for b in data[1:])
        if "@" in email and _is_valid_email(email):
            emails.append(_normalize_email(email))
    return emails


def extract_mailto(html: str) -> Optional[str]:
    """Pull the first email out of a mailto: link, if it's actually valid —
    an explicit mailto: is a stronger signal than a loose text match, but its
    href value still isn't guaranteed to be real (template placeholders,
    tracking links)."""
    decoded = _decode_entities(html or "")
    match = MAILTO_RE.search(decoded)
    if not match:
        return None
    candidate = unquote(match.group(1)).split("?")[0]
    candidate = _normalize_email(candidate)
    return candidate if _is_valid_email(candidate) else None


def extract_tel(html: str) -> Optional[str]:
    """Pull the first phone number out of a tel: link, if it's actually valid.
    Unlike first_valid_phone, a tel: href is legitimately allowed to be a bare
    digit run (that's the normal format for tel: links) — only the digit-count
    check applies here, not the "must be formatted" heuristic."""
    decoded = _decode_entities(html or "")
    match = TEL_RE.search(decoded)
    if not match:
        return None
    candidate = unquote(match.group(1))
    return candidate if _is_valid_phone_digits(candidate) else None


_NOT_A_BUSINESS_SITE = NON_WEBSITE_DOMAINS | DIRECTORY_DOMAINS


def is_own_website(url: str) -> bool:
    if not url:
        return False
    host = urlparse(url).netloc.lower().removeprefix("www.")
    if not host:
        return False
    if any(host == d or host.endswith("." + d) for d in _NOT_A_BUSINESS_SITE):
        return False
    if any(marker in host for marker in DIRECTORY_MARKERS):
        return False
    return True


def clean_business_name(name: str) -> str:
    """Businesses commonly stuff their Google Maps/web-search listing name with
    keyword spam for local SEO, e.g. "Bhatti Dental Clinic | Best Dental Clinic
    in Karachi | Female Dentist in Karachi". The pipe is a reliable signal for
    this pattern (real business names essentially never contain a literal
    "|"), so keep only the first segment — the actual name."""
    if not name:
        return name
    return name.split("|", 1)[0].strip() or name.strip()


def find_social_links(html: str) -> dict[str, str]:
    links: dict[str, str] = {}
    for platform, pattern in SOCIAL_LINK_PATTERNS.items():
        match = pattern.search(html or "")
        if match:
            # Trim trailing HTML-ish junk a greedy match can pick up (quotes are
            # excluded by the pattern already, but stray punctuation isn't).
            links[platform] = match.group(0).rstrip(').,;')
    return links
