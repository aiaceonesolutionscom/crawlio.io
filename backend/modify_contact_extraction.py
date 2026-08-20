#!/usr/bin/env python3
import sys
import os

# Read the original backup
bak_path = 'E:\\crawlio.io\\backend\\app\\services\\discovery\\contact_extraction.py.bak'
with open(bak_path, 'r', encoding='utf-8') as f:
    original = f.read()

# New functions to append
new_funcs = r"""

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
    if not name:
        return name
    return name.split("|", 1)[0].strip() or name.strip()


def find_social_links(html: str) -> dict[str, str]:
    links: dict[str, str] = {}
    for platform, pattern in SOCIAL_LINK_PATTERNS.items():
        match = pattern.search(html or "")
        if match:
            links[platform] = match.group(0).rstrip(').,;')
    return links


# Website contact extraction pipeline (section 2.4 spec)
import asyncio
from urllib.parse import urlparse, urljoin

from app.services.discovery.website_scraper_service import fetch_plain, extract_contact_from_website
from app.services.discovery.structured_extraction import extract_from_jsonld


def normalize_website_url(url: str) -> str:
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


def _add_url(discovered: list, seen: set, url: str) -> None:
    absolute = urljoin(discovered[0] if discovered else "", url) if not url.startswith(("http://", "https://")) else url
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


CONTACT_SUBPATHS = ["/contact", "/contact-us", "/contact.html", "/about", "/about-us"]

CONTACT_HINT_RE = re.compile(
    r"contact|get\s*[-_]?in\s*touch|getintouch|reach\s*us|connect\s*with|about\s*us|say\s*hello|تواصل",
    re.IGNORECASE,
)

_MAX_PAGES_PER_SITE = 8


def discover_contact_urls(homepage_url: str, homepage_html: str, max_urls: int = _MAX_PAGES_PER_SITE) -> list[str]:
    discovered: list[str] = []
    seen: set[str] = set()
    for subpath in CONTACT_SUBPATHS:
        _add_url(discovered, seen, subpath)
    for href, text in _extract_links(homepage_html):
        if len(discovered) >= max_urls:
            break
        if not _same_origin(homepage_url, href):
            continue
        haystack = f"{href} {text}"
        if CONTACT_HINT_RE.search(haystack):
            _add_url(discovered, seen, href)
    return discovered[:max_urls]


def aggregate_contacts(
    pages: list[str],
    website: str,
    country_code: Optional[str] = None,
) -> dict:
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


def best_email(text: str, website: Optional[str] = None, preferred: Optional[str] = None,
               caller_ip: Optional[str] = None) -> Optional[str]:
    candidates = collect_emails(text)
    if not candidates:
        return None
    if preferred and _normalize_email(preferred) in candidates:
        return _normalize_email(preferred)
    def _sort_key(email: str):
        return _email_score(email, website, caller_ip)
    ranked = sorted(candidates, key=_sort_key, reverse=True)
    top = ranked[0]
    if _is_disposable_email(top) and _is_placeholder_email(top):
        return None
    return top


def first_valid_email(text: str) -> Optional[str]:
    return best_email(text)


def _phone_digits(candidate: str) -> str:
    return re.sub(r"\D", "", candidate)


def _is_valid_phone_digits(candidate: str) -> bool:
    digits = _phone_digits(candidate)
    return 7 <= len(digits) <= 15


def _looks_fake_phone(digits: str) -> bool:
    if not digits:
        return True
    if len(digits) < 7:
        return True
    if len(set(digits)) == 1:
        return True
    if digits in {"1234567", "12345678", "123456789", "0123456789"}:
        return True
    if digits.startswith(("000", "111", "999")) and len(digits) >= 10:
        return True
    return False


def _phone_country_penalty(candidate: str, country_code: Optional[str]) -> int:
    if not country_code:
        return 0
    entry = _COUNTRY_DIAL.get(str(country_code).upper())
    if not entry:
        return 0
    dial, national = entry
    digits = _phone_digits(candidate)
    if candidate.strip().startswith(dial) or digits.startswith(dial.lstrip("+")):
        remaining = len(digits) - len(dial.lstrip("+"))
        if remaining > 0 and not (national - 2 <= remaining <= national + 2):
            return -20
        return 5
    if len(digits) == national + 2:
        return -10
    return 0


_Phone_CONTEXT_RE = re.compile(
    r"(?:tel|phone|call|contact|whatsapp|mobile|cell|hotline|helpline)\s*[:\-]?\s*$",
    re.IGNORECASE,
)
_PHONE_CONTEXT_WINDOW = 20


def collect_phones(text: str, max_candidates: int = 30) -> list[str]:
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
        if candidate == digits:
            window = decoded[max(0, match.start() - _PHONE_CONTEXT_WINDOW):match.start()]
            if not _Phone_CONTEXT_RE.search(window):
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
        score += 5
    elif candidate.strip().startswith(("0", "(")):
        score += 2
    score += _phone_country_penalty(candidate, country_code)
    if candidate.strip().startswith("555-") or candidate.strip().endswith("-5555"):
        score -= 20
    return score


def best_phone(text: str, country_code: Optional[str] = None, preferred: Optional[str] = None) -> Optional[str]:
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
    return best_phone(text)


def decode_cfemail(html: str) -> list[str]:
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
    decoded = _decode_entities(html or "")
    match = MAILTO_RE.search(decoded)
    if not match:
        return None
    candidate = unquote(match.group(1)).split("?")[0]
    candidate = _normalize_email(candidate)
    return candidate if _is_valid_email(candidate) else None


def extract_tel(html: str) -> Optional[str]:
    decoded = _decode_entities(html or "")
    match = TEL_RE.search(decoded)
    if not match:
        return None
    candidate = unquote(match.group(1))
    return candidate if _is_valid_phone_digits(candidate) else None


def fetch_contact_emails(url: str, country_code: Optional[str] = None,
                         caller_ip: Optional[str] = None) -> dict:
    target = normalize_website_url(url)
    if not target:
        return {
            "email": None,
            "email_candidates": [],
            "phone": None,
            "phone_candidates": [],
            "website": None,
            "address": None,
            "hours": None,
            "social_links": {},
            "grade": "C",
            "page_text": "",
        }

    try:
        plain_result = asyncio.run(fetch_plain(target, country_code, _MAX_PAGES_PER_SITE))
    except Exception:
        plain_result = None

    if plain_result is None or plain_result.get("email") is None:
        try:
            browser_result = asyncio.run(extract_contact_from_website(target, country_code, _MAX_PAGES_PER_SITE))
        except Exception:
            browser_result = None
    else:
        browser_result = None

    result = plain_result if plain_result is not None else (browser_result or {})

    if result is None:
        result = {}

    all_html = ""
    if plain_result and plain_result.get("page_text"):
        all_html += plain_result["page_text"] + "\n"
    if browser_result and browser_result.get("page_text"):
        all_html += browser_result["page_text"] + "\n"

    if plain_result and plain_result.get("page_text"):
        try:
            structured = extract_from_jsonld(plain_result["page_text"])
            if structured.get("email") and not result.get("email"):
                result["email"] = structured["email"]
            if structured.get("phone") and not result.get("phone"):
                result["phone"] = structured["phone"]
            if structured.get("address") and not result.get("address"):
                result["address"] = structured["address"]
            if structured.get("hours") and not result.get("hours"):
                result["hours"] = structured["hours"]
            if structured.get("website") and not result.get("website"):
                result["website"] = structured["website"]
            if structured.get("social_links"):
                result["social_links"] = {**result.get("social_links", {}), **structured["social_links"]}
        except Exception:
            pass

    best = best_email(all_html, website=target, caller_ip=caller_ip)
    result["email"] = best if best else result.get("email")

    all_emails = collect_emails(all_html)
    seen = set()
    email_candidates = []
    for e in all_emails:
        norm = _normalize_email(e)
        if norm not in seen:
            seen.add(norm)
            email_candidates.append(norm)
        if len(email_candidates) >= 20:
            break
    result["email_candidates"] = email_candidates

    all_phones = collect_phones(all_html) if all_html else []
    seen_phones = set()
    phone_candidates = []
    for p in all_phones:
        dp = _phone_digits(p)
        if dp not in seen_phones:
            seen_phones.add(dp)
            phone_candidates.append(p)
        if len(phone_candidates) >= 10:
            break
    result["phone_candidates"] = phone_candidates

    if result.get("phone") is None:
        result["phone"] = best_phone(all_html, country_code=country_code) or result.get("phone")

    has_email = result.get("email") is not None and result.get("email") != ""
    has_phone = result.get("phone") is not None and result.get("phone") != ""
    has_website = result.get("website") is not None and result.get("website") != ""
    has_address = result.get("address") is not None and result.get("address") != ""

    if has_email and has_phone and has_website:
        result["grade"] = "A"
    elif has_phone and has_address and has_website:
        result["grade"] = "B"
    else:
        result["grade"] = "C"

    result["website"] = result.get("website") or target
    result["page_text"] = all_html[:24000]

    return result
"""

# Write the new file
target_path = 'E:\\crawlio.io\\backend\\app\\services\\discovery\\contact_extraction.py'
with open(target_path, 'w', encoding='utf-8') as f:
    f.write(original + new_funcs)

print(f"File written successfully, length: {len(original + new_funcs)}")