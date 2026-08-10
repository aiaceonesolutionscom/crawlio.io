"""AI-assisted contact disambiguation.

Regex scraping collects *candidates*; this service picks the *right one* and
extracts the richer profile a lead-generation tool actually wants (description,
hours, socials). It is deliberately only ever asked to read text we already have
(an own-website scrape or Tavily's raw content) — it never searches, so it can
never invent data. Every field is optional and must be literally present in the
text we hand it.
"""
import json
import logging
import re
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"

EXTRACTION_PROMPT = (
    "You extract verified business contact details from raw web page text. "
    "Given the business name, city, and text, return a JSON object with these "
    "fields (all optional — use null when the value is not present in the text): "
    '"email" (the single best business email; prefer one whose domain matches the '
    'business website; NEVER a "noreply"/"no-reply" system address, a template '
    'placeholder like "yourname@example.com", or a theme/agency email unless it is '
    "clearly the business's own), "
    '"phone" (single best business phone; prefer the number explicitly listed as '
    "the business's contact, not a fax or a random formatted number), "
    '"website" (the business\'s own site, if a URL appears in the text), '
    '"address" (street/city full address), '
    '"hours" (opening hours as a short string, e.g. "Mon-Sat 9am-7pm"), '
    '"description" (one sentence describing what the business does), '
    '"social_links" (object of platform -> full URL, e.g. {{"instagram": "..."}} — '
    'only real profile pages from the text), '
    '"confidence" (0.0 to 1.0 — how sure you are the extracted email/phone are '
    "the business's real contact). "
    f"Business: the business is named \"{{name}}\" in {{city}}.\n"
    "Rules: NEVER invent a value that is not literally in the text. Do not return "
    "an email or phone from a different business mentioned in the text. Respond "
    "with ONLY the JSON object."
)

# Raw page content is dominated by base64 image data URIs and markdown filler —
# neither carries contact data, and both burn token budget.
_DATA_URI_RE = re.compile(r"data:image/[^)\"'\s]+", re.IGNORECASE)
_BLANK_LINES_RE = re.compile(r"\n{3,}")
MAX_CONTENT_CHARS = 24_000


def _clean_text(raw: str) -> str:
    cleaned = _DATA_URI_RE.sub("", raw or "")
    cleaned = _BLANK_LINES_RE.sub("\n\n", cleaned)
    return cleaned[:MAX_CONTENT_CHARS]


def _platform_for_url(url: str) -> Optional[str]:
    from urllib.parse import urlparse

    host = urlparse(url).netloc.lower().removeprefix("www.")
    mapping = {
        "facebook.com": "facebook",
        "instagram.com": "instagram",
        "linkedin.com": "linkedin",
        "twitter.com": "twitter",
        "x.com": "twitter",
        "youtube.com": "youtube",
        "tiktok.com": "tiktok",
    }
    for domain, platform in mapping.items():
        if host == domain or host.endswith("." + domain):
            return platform
    return None


async def extract_contact(
    text: str,
    name: str,
    city: str,
    website: Optional[str] = None,
    extra_socials: Optional[dict[str, str]] = None,
) -> dict:
    """Ask Mistral to read raw page/search content and return the business's
    single best contact + profile. Returns an empty dict on any failure — the
    caller keeps whatever regex scraping already found."""
    if not settings.mistral_api_key:
        return {}
    cleaned = _clean_text(text)
    if len(cleaned) < 150:
        return {}

    context = []
    if website:
        context.append(f"Known website: {website}")
    if extra_socials:
        context.append(f"Known socials: {json.dumps(extra_socials)}")
    context.append(f"Raw content:\n{cleaned}")
    user_content = "\n\n".join(context)

    payload = {
        "model": "mistral-small-latest",
        "messages": [
            {
                "role": "system",
                "content": EXTRACTION_PROMPT.format(name=name, city=city),
            },
            {"role": "user", "content": user_content},
        ],
        "response_format": {"type": "json_object"},
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                MISTRAL_URL,
                headers={"Authorization": f"Bearer {settings.mistral_api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        logger.warning("AI contact extraction failed for %s: %s", name, exc)
        return {}

    if not isinstance(parsed, dict):
        return {}

    email = str(parsed.get("email") or "").strip().lower() or None
    phone = str(parsed.get("phone") or "").strip() or None
    website_found = str(parsed.get("website") or "").strip() or None
    address = str(parsed.get("address") or "").strip() or None
    hours = str(parsed.get("hours") or "").strip() or None
    description = str(parsed.get("description") or "").strip() or None

    social_links: dict[str, str] = {}
    socials_raw = parsed.get("social_links")
    if isinstance(socials_raw, dict):
        for platform, url in socials_raw.items():
            if isinstance(url, str) and url.startswith(("http://", "https://")):
                social_links[platform.lower()] = url
    elif isinstance(socials_raw, list):
        for url in socials_raw:
            if isinstance(url, str):
                platform = _platform_for_url(url)
                if platform:
                    social_links[platform] = url

    try:
        confidence = float(parsed.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    return {
        "email": email,
        "phone": phone,
        "website": website_found,
        "address": address,
        "hours": hours,
        "description": description,
        "social_links": social_links,
        "confidence": confidence,
    }


async def extract_from_tavily_results(name: str, city: str, results: list[dict]) -> dict:
    """Fold a set of Tavily search results (snippet + optional raw content) into
    one text blob and let AI extract the business's contact profile from it."""
    parts: list[str] = []
    for result in results:
        title = result.get("title") or ""
        url = result.get("url") or ""
        content = result.get("content") or result.get("raw_content") or ""
        if title:
            parts.append(title)
        if url:
            parts.append(url)
        if content:
            parts.append(content)
    text = "\n\n".join(parts)
    if len(_clean_text(text)) < 300:
        return {}
    return await extract_contact(text, name, city)
