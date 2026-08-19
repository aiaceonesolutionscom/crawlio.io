"""Person-level team contact extraction — the "enrichment" half of Apollo.

Beyond a business's generic info@ address, sales teams want the *people*: the
founder, the sales director, the ops lead. This module, given a business
website's HTML (homepage + /about + /team), extracts likely person names and any
email addresses shown near them, and generates + verifies predicted
first.last@domain addresses for each named person (Sprint 4 email_patterns +
smtp_verify). The result is a list of person records a sales pipeline can act on
directly — all free, no API key.
"""
import logging
import re
from typing import Optional

from app.services.discovery.crawlers.email_patterns import person_email_candidates
from app.services.discovery.crawlers.smtp_verify import SMTPVerifier

logger = logging.getLogger(__name__)

_NAME_RE = re.compile(
    r"\b([A-Z][a-z]{2,})\s+([A-Z][a-z]{2,})\b"
)
_EMAIL_IN_SAME_PARAGRAPH_RE = re.compile(
    r"([A-Z][a-z]{2,})\s+([A-Z][a-z]{2,})[^\n]{0,120}?([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})"
)
_ROLE_WORDS = {
    "founder", "ceo", "director", "manager", "head", "lead", "sales",
    "marketing", "operations", "support", "owner", "co-founder", "cto",
    "president", "partner", "associate", "coordinator", "specialist",
}


def _strip_titles(name: str) -> str:
    return re.sub(r"\b(Dr\.|Mr\.|Mrs\.|Ms\.|Miss|Prof\.)\b", "", name).strip()


def extract_people_from_html(html: str, domain: str) -> list[dict]:
    """Return a list of {name, role?, email?, source} person records found in a
    page. Uses emails shown next to a name when present; otherwise leaves email
    empty so callers can run the prediction+verify pipeline."""
    if not html or not domain:
        return []

    people: list[dict] = []
    seen: set[str] = set()

    # 1) Names that appear with an email in the same short window — high
    #    confidence: "John Smith | john@company.com".
    for m in _EMAIL_IN_SAME_PARAGRAPH_RE.finditer(html):
        first, last, email = m.group(1), m.group(2), m.group(3).lower()
        name = f"{first} {last}"
        if name in seen:
            continue
        seen.add(name)
        people.append({"name": name, "email": email, "role": "", "source": "page_email"})

    # 2) General names near role words (team/about sections) — these are the
    #    candidates the predictor runs on.
    for m in _NAME_RE.finditer(html):
        name = _strip_titles(m.group(0))
        if name in seen or len(seen) > 40:
            continue
        seen.add(name)
        people.append({"name": name, "email": None, "role": "", "source": "name_only"})

    return people


async def enrich_people(
    html_pages: list[str],
    domain: str,
    verify: bool = True,
    max_people: int = 5,
    from_addr: str = "verify@crawlio.io",
) -> list[dict]:
    """Extract people from a business's pages and verify predicted addresses.

    Returns up to `max_people` person records ordered by confidence: people
    whose email was literally on the page first, then people whose predicted
    first.last@domain passed the SMTP check, then predicted-but-unverifiable.
    """
    domain = (domain or "").lower().replace("www.", "")
    if not domain:
        return []

    combined_html = "\n".join(html_pages)
    page_people = extract_people_from_html(combined_html, domain)

    # People whose email was on the page are already strong.
    verified: list[dict] = []
    for person in page_people:
        if person["email"] and len(verified) < max_people:
            person["email_verified"] = "on_page"
            verified.append(person)

    # Predict + verify for named people without an email.
    to_verify = [p for p in page_people if not p["email"]]
    verifier = SMTPVerifier() if verify else None
    for person in to_verify[: max(10, max_people * 3)]:
        if len(verified) >= max_people:
            break
        candidates = person_email_candidates(person["name"], domain)
        if not candidates:
            continue
        # Try up to a handful of most-likely patterns, stop at the first valid.
        if verifier is not None:
            statuses = await verifier.verify_many(candidates[:6], from_addr=from_addr)
            accepted = next((addr for addr, st in statuses.items() if st == "valid"), None)
            if accepted:
                person["email"] = accepted
                person["email_verified"] = "smtp"
                verified.append(person)
        else:
            # No SMTP pass — still offer the most likely pattern, unverified.
            person["email"] = candidates[0]
            person["email_verified"] = "predicted"
            verified.append(person)

    # Drop the on-page-but-rejected placeholders (info@, noreply@ etc. are not
    # *people*; the predictor + role filter keeps this to humans).
    result: list[dict] = []
    for person in verified:
        if person.get("email") and re.match(r".*@.+", person["email"]):
            result.append(person)
    return result[:max_people]
