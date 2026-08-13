import hmac
import hashlib
import logging
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.email import EmailMessage
from app.db.models.workspace import Workspace
from app.db.session import get_session
from app.schemas.automation import InboundLeadCapture
from app.schemas.lead import LeadCreate
from app.services import lead_service
from app.workers.tasks_scoring import score_lead_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/leads/{workspace_id}", status_code=status.HTTP_201_CREATED)
async def capture_inbound_lead(
    workspace_id: str,
    payload: InboundLeadCapture,
    session: Annotated[AsyncSession, Depends(get_session)],
    token: str = Query(...)
):
    """Public endpoint for external forms/integrations to push a lead into a
    workspace. Auth is the workspace's own webhook_token (query param), not a
    Clerk session — the caller is a server or form handler, not a logged-in user."""
    result = await session.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = result.scalar_one_or_none()
    if workspace is None or workspace.webhook_token != token:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown workspace or webhook token")

    lead = await lead_service.create_lead(
        session,
        workspace,
        LeadCreate(
            name=payload.name,
            email=payload.email,
            phone=payload.phone,
            source=payload.source
        )
    )
    try:
        score_lead_task.delay(lead.id)
    except Exception as exc:
        logger.warning("Could not dispatch scoring for webhook lead %s: %s", lead.id, exc)
    return {"id": lead.id, "status": "captured"}


_BREVO_STATUS_BY_EVENT = {
    "delivered": "delivered",
    "hard_bounce": "bounced",
    "soft_bounce": "bounced",
    "blocked": "blocked",
    "spam": "complained",
    "deferred": "delayed",
    "error": "failed"
}


@router.post("/brevo")
async def brevo_event_webhook(payload: dict[str, Any], session: Annotated[AsyncSession, Depends(get_session)]):
    """Receives Brevo transactional-email delivery-status events and updates the
    matching EmailMessage row. Brevo webhooks aren't signed by default; signature
    verification is left for production hardening once one is configured."""
    event_type = payload.get("event", "")
    new_status = _BREVO_STATUS_BY_EVENT.get(event_type)
    provider_message_id = payload.get("message-id")
    if new_status is None or not provider_message_id:
        return {"received": True, "applied": False}

    result = await session.execute(
        select(EmailMessage).where(EmailMessage.provider_message_id == provider_message_id)
    )
    message = result.scalar_one_or_none()
    if message is None:
        return {"received": True, "applied": False}

    message.status = new_status
    if new_status == "delivered":
        message.sent_at = datetime.now(timezone.utc)
    await session.commit()
    return {"received": True, "applied": True}


def _verify_whatsapp_signature(raw_body: bytes, signature_header: str) -> bool:
    """Meta signs every webhook POST with X-Hub-Signature-256 = sha256=HMAC(
    meta_app_secret, raw_body). Reject anything that doesn't match."""
    if not settings.meta_app_secret or not signature_header:
        return False
    expected = "sha256=" + hmac.new(
        settings.meta_app_secret.encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


@router.get("/whatsapp")
async def whatsapp_verify(
    hub_mode: str = Query("", alias="hub.mode"),
    hub_verify_token: str = Query("", alias="hub.verify_token"),
    hub_challenge: str = Query("", alias="hub.challenge"),
):
    """Meta webhook verification handshake. Meta GETs this URL when we hit
    "Verify and Save"; we must echo back hub.challenge when the verify token
    matches whatsapp_verify_token, else Meta rejects the callback URL."""
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        return Response(content=hub_challenge, media_type="text/plain")
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verification failed")


@router.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    """Receive inbound WhatsApp messages (and delivery/read callbacks).

    Routing: Meta sends EVERY workspace's messages to this one URL, so we look
    up the connected account by payload['entry'][]['changes'][]['value']
    ['metadata']['phone_number_id'] and process under that account's workspace.
    """
    raw_body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not _verify_whatsapp_signature(raw_body, signature):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature")

    import json
    payload = json.loads(raw_body or "{}")

    messages_handled = 0
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            metadata = value.get("metadata") or {}
            phone_number_id = metadata.get("phone_number_id")
            if not phone_number_id:
                continue

            from app.db.models.whatsapp import WhatsAppAccount

            result = await session.execute(
                select(WhatsAppAccount).where(WhatsAppAccount.phone_number_id == phone_number_id)
            )
            account = result.scalar_one_or_none()
            if account is None:
                logger.warning("whatsapp webhook: unknown phone_number_id %s", phone_number_id)
                continue

            # Delivery / read status callbacks -> update last message state.
            statuses = value.get("statuses") or []
            for st in statuses:
                wamid = st.get("id")
                delivery = st.get("status", "")
                if wamid and delivery in ("sent", "delivered", "read"):
                    await _update_whatsapp_message_status(session, account, wamid, delivery)

            # Inbound text messages -> store + let the AI agent answer.
            for msg in value.get("messages", []):
                from_phone = msg.get("from", "")
                wamid = msg.get("id", "")
                msg_type = msg.get("type", "")
                text_obj = msg.get("text") or {}
                body = (text_obj.get("body") or "").strip()
                if not body:
                    continue

                await _handle_inbound_whatsapp(
                    session, account, from_phone, wamid, body
                )
                messages_handled += 1

    await session.commit()
    return {"received": True, "messages_handled": messages_handled}


async def _update_whatsapp_message_status(
    session: AsyncSession, account: Any, wamid: str, delivery: str
) -> None:
    from app.db.models.whatsapp import WhatsAppConversation, WhatsAppConversationMessage

    result = await session.execute(
        select(WhatsAppConversationMessage).where(
            WhatsAppConversationMessage.provider_message_id == wamid
        )
    )
    message = result.scalar_one_or_none()
    if message is not None:
        message.is_approved = True
        if delivery == "delivered":
            message.sent_at = datetime.now(timezone.utc)


async def _handle_inbound_whatsapp(
    session: AsyncSession,
    account: Any,
    from_phone: str,
    wamid: str,
    body: str,
) -> None:
    """Route one inbound message: find/create the conversation, dedup, store,
    then hand off to the AI auto-reply pipeline (Step 6)."""
    from app.services.whatsapp_conversation_service import find_or_create_conversation
    from app.services.whatsapp_ai_service import handle_webhook_message

    conversation = await find_or_create_conversation(
        session,
        workspace_id=account.workspace_id,
        whatsapp_account_id=account.id,
        customer_phone=from_phone,
    )
    await handle_webhook_message(session, account, conversation, wamid, body)
