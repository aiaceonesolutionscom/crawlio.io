import logging
from urllib.parse import urljoin

import httpx

from app.services.contact_extraction import (
    extract_mailto,
    extract_tel,
    find_social_links,
    first_valid_email,
    first_valid_phone,
)

logger = logging.getLogger(__name__)

SCRAPE_TIMEOUT = 8.0
SCRAPE_HEADERS = {
    # A real browser UA — some small-business hosting (Wix, GoDaddy sites) 406s
    # bare httpx/requests-style user agents, same class of issue seen with Overpass.
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
}
# Checked in order, stopping as soon as email+phone+socials are all found —
# a contact/about page is far more likely to list an email than the homepage.
CONTACT_SUBPATHS = ["/contact", "/contact-us", "/contact.html", "/about", "/about-us"]


async def _fetch_html(client: httpx.AsyncClient, url: str) -> str:
    try:
        resp = await client.get(url)
    except httpx.HTTPError as exc:
        logger.info("Website scrape failed for %s: %s", url, exc)
        return ""
    if resp.status_code >= 400 or "text/html" not in resp.headers.get("content-type", ""):
        return ""
    return resp.text


def _extract(html: str) -> dict:
    return {
        "email": extract_mailto(html) or first_valid_email(html),
        "phone": extract_tel(html) or first_valid_phone(html),
        "social_links": find_social_links(html),
    }


async def extract_contact_from_website(url: str) -> dict:
    """Fetch a business's own website (homepage, then /contact and /about if
    still missing something) and pull whatever contact info + social links are
    on the page — free, no API key, and low-risk since it's a GET to public
    pages the business itself put up (not scraping a search engine)."""
    target = url if url.startswith(("http://", "https://")) else f"https://{url}"

    async with httpx.AsyncClient(
        timeout=SCRAPE_TIMEOUT, headers=SCRAPE_HEADERS, follow_redirects=True
    ) as client:
        html = await _fetch_html(client, target)
        if not html:
            return {}

        found = _extract(html)

        for subpath in CONTACT_SUBPATHS:
            if found.get("email") and found.get("phone") and found.get("social_links"):
                break
            sub_html = await _fetch_html(client, urljoin(target, subpath))
            if not sub_html:
                continue
            sub_found = _extract(sub_html)
            found["email"] = found.get("email") or sub_found.get("email")
            found["phone"] = found.get("phone") or sub_found.get("phone")
            found["social_links"] = {**sub_found.get("social_links", {}), **found.get("social_links", {})}

    return {
        "email": found.get("email"),
        "phone": found.get("phone"),
        "social_links": found.get("social_links") or {},
    }
