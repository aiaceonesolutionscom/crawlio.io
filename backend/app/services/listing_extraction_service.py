import json
import logging
import re

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = (
    "You extract real business listings from web page content (business directories, "
    "\"best of\" articles, review sites). Given a niche, a city, and raw page text, "
    "return a JSON object with one field \"businesses\": an array of objects, each with "
    "\"name\" (required), \"phone\", \"email\", \"website\", \"address\" (all optional — "
    "omit a field or use null if it is not present in the text). Rules: only include "
    "businesses that plausibly match the niche and city. Never invent a phone, email, "
    "address or website that is not explicitly present in the text. Skip navigation "
    "links, ads, unrelated content, and duplicate entries. Return at most {max_items} "
    "businesses. Respond with ONLY the JSON object."
)

# Raw page content pulled from real sites is dominated by base64 image data
# URIs and markdown table filler — neither carries any business data, and both
# waste a large share of the token budget we send to the model.
_DATA_URI_RE = re.compile(r"data:image/[^)\"'\s]+", re.IGNORECASE)
_BLANK_LINES_RE = re.compile(r"\n{3,}")
MAX_CONTENT_CHARS = 18_000


def _clean_raw_content(raw: str) -> str:
    cleaned = _DATA_URI_RE.sub("", raw)
    cleaned = _BLANK_LINES_RE.sub("\n\n", cleaned)
    return cleaned[:MAX_CONTENT_CHARS]


async def extract_businesses(niche: str, city: str, raw_content: str, max_items: int = 15) -> list[dict]:
    """Ask Mistral to pull individual business listings (name/phone/email/
    website/address) out of a directory or listicle page's raw text. This is
    what makes pages we can't parse with a fixed regex (every directory site
    formats its listings differently) usable as a discovery source."""
    if not settings.mistral_api_key or not raw_content:
        return []

    cleaned = _clean_raw_content(raw_content)
    if len(cleaned) < 200:
        return []

    payload = {
        "model": "mistral-small-latest",
        "messages": [
            {"role": "system", "content": EXTRACTION_PROMPT.format(max_items=max_items)},
            {"role": "user", "content": f"Niche: {niche}\nCity: {city}\n\nPage content:\n{cleaned}"},
        ],
        "response_format": {"type": "json_object"},
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://api.mistral.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.mistral_api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        logger.warning("Business listing extraction failed: %s", exc)
        return []

    businesses = parsed.get("businesses")
    if not isinstance(businesses, list):
        return []

    results = []
    for item in businesses:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        results.append({
            "name": name,
            "phone": str(item.get("phone") or "").strip() or None,
            "email": str(item.get("email") or "").strip() or None,
            "website": str(item.get("website") or "").strip() or None,
            "address": str(item.get("address") or "").strip() or None,
        })
    return results[:max_items]
