"""WhatsApp Cloud API transport (Meta Graph API).

Thin, dependency-free wrapper over the Meta Graph API used by the WhatsApp
agent. Account/token resolution lives in whatsapp_account_service; this module
only talks to graph.facebook.com and returns plain dicts / wamids.

Meta policy that shapes this layer:
  * Business-initiated messages (outreach) MUST use an approved template.
  * Replies inside the 24h customer-session window are free-form text.
  * Every outbound message must be marked read first (best practice).
"""

import json
from typing import Any, Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

_GRAPH = "https://graph.facebook.com"


def _api(access_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }


def graph_version() -> str:
    return settings.whatsapp_graph_version or "v21.0"


async def send_text_message(
    access_token: str,
    phone_number_id: str,
    to_phone: str,
    body: str,
    message_id: Optional[str] = None,
) -> dict[str, Any]:
    """Send a free-form text message (only valid inside a 24h session window)."""
    payload: dict[str, Any] = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone,
        "type": "text",
        "text": {"body": body},
    }
    if message_id:
        payload["context"] = {"message_id": message_id}

    url = f"{_GRAPH}/{graph_version()}/{phone_number_id}/messages"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, headers=_api(access_token), json=payload)
        resp.raise_for_status()
        return resp.json()


async def mark_read(
    access_token: str,
    phone_number_id: str,
    message_id: str,
) -> dict[str, Any]:
    """Mark an inbound message as read (required for good delivery optics)."""
    url = f"{_GRAPH}/{graph_version()}/{phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, headers=_api(access_token), json=payload)
        resp.raise_for_status()
        return resp.json()


async def send_template_message(
    access_token: str,
    phone_number_id: str,
    to_phone: str,
    template_name: str,
    language: str = "en",
    components: Optional[list[dict]] = None,
    message_id: Optional[str] = None,
) -> dict[str, Any]:
    """Send an approved template (the ONLY way to start a business-initiated
    conversation / send outreach outside the 24h window)."""
    payload: dict[str, Any] = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language},
        },
    }
    if components:
        payload["template"]["components"] = components
    if message_id:
        payload["context"] = {"message_id": message_id}

    url = f"{_GRAPH}/{graph_version()}/{phone_number_id}/messages"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, headers=_api(access_token), json=payload)
        resp.raise_for_status()
        return resp.json()


def _template_body(body: str) -> list[dict]:
    """Convert a plain-text template body into Meta's body-component format.

    Supports {{1}}, {{2}}... placeholders as body params. Each distinct
    placeholder gets a text component with the example value set to the
    placeholder itself so Meta's sample-request validation passes."""
    params: list[dict] = []
    for idx in range(1, 11):
        token = f"{{{{{idx}}}}}"
        if token in body:
            params.append({"type": "text", "text": f"[[{idx}]]"})
    if not params:
        return []
    return [{"type": "body", "parameters": params}]


async def create_message_template(
    access_token: str,
    waba_id: str,
    name: str,
    body: str,
    language: str = "en",
    category: str = "MARKETING",
) -> dict[str, Any]:
    """Submit a new message template for approval. Returns Meta's template id;
    the template can only be SENT once its status becomes APPROVED."""
    payload = {
        "name": name,
        "language": language,
        "category": category,
        "components": _template_body(body) or [{"type": "body", "text": body[:1024]}],
    }
    url = f"{_GRAPH}/{graph_version()}/{waba_id}/message_templates"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, headers=_api(access_token), json=payload)
        resp.raise_for_status()
        return resp.json()


async def list_message_templates(
    access_token: str,
    waba_id: str,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """List templates on the WABA (their statuses drive outreach readiness)."""
    url = f"{_GRAPH}/{graph_version()}/{waba_id}/message_templates"
    params = {"limit": limit}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            url, headers=_api(access_token), params=params
        )
        resp.raise_for_status()
        data = resp.json()
    return data.get("data", [])


async def get_phone_number_profile(
    access_token: str,
    phone_number_id: str,
) -> dict[str, Any]:
    """Fetch the business profile (display name, verified status, etc.) for a
    connected number."""
    url = f"{_GRAPH}/{graph_version()}/{phone_number_id}/whatsapp_business_profile"
    params = {"fields": "display_name,about,verified_name"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            url, headers=_api(access_token), params=params
        )
        resp.raise_for_status()
        data = resp.json()
    profile = (data.get("data") or [{}])[0]
    return profile or {}


def normalize_phone(raw: str) -> str:
    """Normalize an inbound/outbound phone to E.164 digits (+ and digits only),
    which is what the Cloud API expects on `to`."""
    digits = "".join(ch for ch in (raw or "") if ch.isdigit() or ch == "+")
    if digits.startswith("00"):
        digits = "+" + digits[2:]
    if not digits.startswith("+"):
        digits = "+" + digits
    return digits


def extract_wamid(payload: dict[str, Any]) -> Optional[str]:
    """Pull the wamid out of a send response (messages[0].id)."""
    msgs = (payload or {}).get("messages") or []
    if msgs:
        return msgs[0].get("id")
    return None


async def send_media_message(
    access_token: str,
    phone_number_id: str,
    to_phone: str,
    media_type: str,
    media_link: str,
    caption: str = "",
    message_id: Optional[str] = None,
) -> dict[str, Any]:
    """Send a media message (image/video/document/audio) by URL."""
    payload: dict[str, Any] = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone,
        "type": media_type,
        media_type: {"link": media_link, "caption": caption} if caption else {"link": media_link},
    }
    if message_id:
        payload["context"] = {"message_id": message_id}
    url = f"{_GRAPH}/{graph_version()}/{phone_number_id}/messages"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, headers=_api(access_token), json=payload)
        resp.raise_for_status()
        return resp.json()
