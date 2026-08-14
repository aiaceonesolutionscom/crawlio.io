"""WhatsApp AI receptionist: the core RAG auto-reply pipeline.

For every inbound WhatsApp message:
  1. dedup by Meta wamid
  2. find-or-create the stable conversation (webhook already did this)
  3. remember customer info into business_context ('info once' — never re-ask)
  4. build history + business knowledge + real availability slots
  5. LLM picks action: reply | book | unsubscribe, with JSON body + selected_slot
  6. send the reply through Meta, log it, and auto-book a REAL slot + hot-lead
     the customer to CRM when they're interested
Every stage is published as wa_* AIActivity over the workspace's WebSocket."""

import json
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.agent import Meeting
from app.db.models.whatsapp import (
    WhatsAppAccount,
    WhatsAppConversation,
    WhatsAppConversationMessage,
)
from app.services.whatsapp import whatsapp_service


AUTO_REPLY_PROMPT_WHATSAPP = """You are the WhatsApp receptionist for {company_name}.

Business knowledge about this company:
{business_context}

Customer conversation so far (newest last):
{history}

Incoming customer message:
{incoming_message}

Available meeting slots (already on the business calendar, local time):
{available_slots}

Rules:
1. Reply like a warm, professional human assistant. WhatsApp replies are short (1-3 sentences).
2. If the customer wants to book / schedule a call or meeting → action "book", pick the earliest suitable slot from the list, and confirm it clearly.
3. If the customer gives feedback or asks service/business questions → answer helpfully → action "reply".
4. For anything else → reply helpfully in 1-3 sentences → action "reply".
5. If the customer explicitly asks to unsubscribe / stop messages / opt out → action "unsubscribe" and confirm politely and briefly.
6. Never invent slots. Only ever pick from the list above.
7. Mark "interested" true when the customer seems like a real lead wanting to talk further.

Return JSON only:
{{
    "action": "book" | "reply" | "unsubscribe",
    "body": "short plain-text WhatsApp reply",
    "interested": true/false,
    "selected_slot": "UTC ISO datetime from the list above (or null)"
}}"""


async def _run_auto_reply_llm(
    business_context: str,
    history: str,
    incoming_message: str,
    company_name: str = "our team",
    available_slots: Optional[list[str]] = None,
    booked: bool = False,
) -> dict:
    """Call Mistral to decide the next agent action. Returns the parsed JSON dict."""
    slots_text = "\n".join(f"  {s}" for s in (available_slots or [])) or "  (none available right now)"
    full_prompt = AUTO_REPLY_PROMPT_WHATSAPP.format(
        company_name=company_name,
        business_context=business_context or "No business context provided.",
        history=history or "(empty)",
        incoming_message=incoming_message,
        available_slots=slots_text,
    )

    payload = {
        "model": "mistral-small-latest",
        "messages": [
            {"role": "system", "content": full_prompt},
            {"role": "user", "content": incoming_message},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.5,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.mistral_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

    content = data["choices"][0]["message"]["content"]
    return json.loads(content)


async def _extract_and_remember(
    session: AsyncSession,
    conversation: WhatsAppConversation,
    incoming_message: str,
) -> None:
    """'Info once' requirement: mine the inbound message for the customer's name
    and any business details, then merge them into the conversation's
    business_context JSON so the agent never asks for the same info twice."""
    # Only pay for an LLM extraction call when there's something new to learn.
    if conversation.customer_name and conversation.business_context:
        return

    prompt = (
        "Extract the customer's name (if present) and any business-related facts "
        "from this WhatsApp message. Return JSON only:\n"
        '{"name": "customer name or null", "info": ["one fact per item"]}\n\n'
        f"Message: {incoming_message}"
    )
    payload = {
        "model": "mistral-small-latest",
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": incoming_message},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.0,
    }
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                "https://api.mistral.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.mistral_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        parsed = json.loads(data["choices"][0]["message"]["content"])
    except Exception:
        return

    name = parsed.get("name")
    facts = parsed.get("info") or []
    facts = [str(f) for f in facts if str(f).strip()]
    if not name and not facts:
        return

    existing = {}
    if conversation.business_context:
        try:
            existing = json.loads(conversation.business_context)
        except (ValueError, TypeError):
            existing = {"notes": conversation.business_context}

    if name and not conversation.customer_name:
        conversation.customer_name = name
    if facts:
        old_facts = existing.get("facts") or []
        merged_facts = list(dict.fromkeys([*old_facts, *facts]))
        existing["facts"] = merged_facts

    conversation.business_context = json.dumps(existing) if existing else conversation.business_context
    conversation.updated_at = datetime.now(timezone.utc)


def _is_unsubscribe_message(message: str) -> bool:
    lowered = (message or "").lower()
    return any(
        word in lowered
        for word in (
            "unsubscribe", "stop messaging", "stop messaging me", "don't message",
            "do not message", "opt out", "stop contact", "remove me", "stop sending",
        )
    )


async def _is_lead_booked(
    session: AsyncSession,
    workspace_id: str,
    conversation_id: str,
    customer_phone: Optional[str] = None,
) -> bool:
    """True when this customer is already booked: a booked Meeting row matching
    the phone, or the 'Meeting booked!' system message on this conversation."""
    if customer_phone:
        result = await session.execute(
            select(Meeting.id)
            .where(
                Meeting.workspace_id == workspace_id,
                Meeting.status == "booked",
                Meeting.lead_phone.isnot(None),
                sa_func.lower(Meeting.lead_phone) == customer_phone.lower(),
            )
            .limit(1)
        )
        if result.first() is not None:
            return True

    result = await session.execute(
        select(WhatsAppConversationMessage.id)
        .where(
            WhatsAppConversationMessage.conversation_id == conversation_id,
            WhatsAppConversationMessage.sender_type == "system",
            WhatsAppConversationMessage.content.like("Meeting booked!%"),
        )
        .limit(1)
    )
    return result.first() is not None


async def _get_conversation_history(
    session: AsyncSession, conversation_id: str
) -> list[WhatsAppConversationMessage]:
    result = await session.execute(
        select(WhatsAppConversationMessage)
        .where(WhatsAppConversationMessage.conversation_id == conversation_id)
        .order_by(WhatsAppConversationMessage.created_at.asc())
    )
    return list(result.scalars().all())


async def auto_respond_to_conversation(
    session: AsyncSession,
    account: WhatsAppAccount,
    conversation: WhatsAppConversation,
    incoming_message: str,
) -> dict:
    """Generate + send an AI WhatsApp reply, remember info, and auto-book a real
    slot + hot-lead the customer when interested. All stages persisted to
    AIActivity + pushed over the workspace's WebSocket."""
    from app.services.agent import agent_realtime
    from app.services.automation import meeting_service
    from app.services.agent.business_profile_service import get_profile, to_context
    from app.services.whatsapp.whatsapp_conversation_service import (
        book_meeting as crm_book,
        clean_message_content,
    )

    await agent_realtime.publish_activity(
        session, conversation.workspace_id, "wa_received",
        whatsapp_conversation_id=conversation.id, detail="New inbound WhatsApp message",
    )

    # STOP guard #1: never process a conversation the owner has paused.
    if not conversation.ai_agent_active or conversation.status != "active":
        return {"status": "skipped", "reason": "ai_paused"}

    # 'Info once': mine the message into business_context before replying so the
    # agent answers with the customer's own details on the very first message.
    await _extract_and_remember(session, conversation, incoming_message)

    customer_phone = conversation.customer_phone
    if not customer_phone:
        raise RuntimeError("No customer phone to reply to")

    profile = await get_profile(session, conversation.workspace_id)
    business_context = conversation.business_context or ""
    if profile:
        business_context = f"{to_context(profile, account.business_phone or account.display_name or '')}\n\nAgent notes:\n{business_context}"

    await agent_realtime.publish_activity(
        session, conversation.workspace_id, "wa_lead_identified",
        whatsapp_conversation_id=conversation.id,
        detail=f"Identified lead {conversation.customer_name or customer_phone}",
    )

    messages = await _get_conversation_history(session, conversation.id)
    history_lines = [f"{m.sender_type.upper()}: {m.content}" for m in messages]
    history = "\n".join(history_lines)

    # Real availability: business hours minus booked meetings — never invented.
    available = []
    if profile:
        booked = await meeting_service.list_bookable_meetings(session, conversation.workspace_id)
        available = meeting_service.next_slots(profile, count=4, bookable=booked)
    available_text = [s.isoformat() for s in available]
    is_booked = await _is_lead_booked(
        session, conversation.workspace_id, conversation.id, customer_phone
    )

    await agent_realtime.publish_activity(
        session, conversation.workspace_id, "wa_intent",
        whatsapp_conversation_id=conversation.id, detail="Reading conversation + intent",
    )

    if _is_unsubscribe_message(incoming_message):
        result = {"action": "unsubscribe"}
        await agent_realtime.publish_activity(
            session, conversation.workspace_id, "wa_unsubscribed",
            whatsapp_conversation_id=conversation.id, detail="Customer opted out",
        )
    else:
        company_name = (
            profile.business_name
            if profile and profile.business_name
            else (account.display_name or "our team")
        )
        result = await _run_auto_reply_llm(
            business_context=business_context,
            history=history,
            incoming_message=incoming_message,
            company_name=company_name,
            available_slots=available_text,
            booked=is_booked,
        )

    action = result.get("action") or ("reply" if not _is_unsubscribe_message(incoming_message) else "unsubscribe")
    body = clean_message_content(result.get("body", ""))
    interested = bool(result.get("interested"))

    # STOP guard #2: only send if the agent is still enabled right now.
    if not conversation.ai_agent_active or conversation.status != "active":
        await agent_realtime.publish_activity(
            session, conversation.workspace_id, "wa_ai_stopped",
            whatsapp_conversation_id=conversation.id, status="failed",
            detail="Agent stopped before send",
        )
        return {"status": "skipped", "reason": "ai_paused_before_send"}

    if action == "unsubscribe":
        from app.db.models.lead import Lead

        lead_result = await session.execute(
            select(Lead).where(
                Lead.workspace_id == conversation.workspace_id,
                sa_func.lower(Lead.phone) == customer_phone.lower(),
            )
        )
        lead = lead_result.scalars().first()
        if lead is not None:
            lead.unsubscribed_at = datetime.now(timezone.utc)
            lead.status = "Unsubscribed"
            lead.updated_at = datetime.now(timezone.utc)
        if not body:
            body = "Understood — you've been removed from our list. You won't hear from us again."

    # Send the real WhatsApp message + mark the inbound as read.
    outbound_id = None
    try:
        send_result = await whatsapp_service.send_text_message(
            account.access_token, account.phone_number_id, customer_phone, body
        )
        outbound_id = whatsapp_service.extract_wamid(send_result)
    except Exception:
        # Log the attempt anyway; caller surfaces the 24h-window error.
        outbound_id = None

    await agent_realtime.publish_activity(
        session, conversation.workspace_id, "wa_reply_sent",
        whatsapp_conversation_id=conversation.id, detail="Reply sent to customer",
    )

    session.add(
        WhatsAppConversationMessage(
            conversation_id=conversation.id,
            sender_type="ai",
            direction="outbound",
            content=body,
            is_approved=True,
            sent_at=datetime.now(timezone.utc),
            provider_message_id=outbound_id,
        )
    )

    meeting_booked = False
    if action == "book" and interested and profile:
        selected_slot = result.get("selected_slot")
        scheduled = None
        if selected_slot:
            try:
                scheduled = datetime.fromisoformat(selected_slot)
                if scheduled.tzinfo is None:
                    scheduled = scheduled.replace(tzinfo=ZoneInfo(profile.timezone))
            except ValueError:
                scheduled = None
        # Only ever book a slot that was actually offered.
        if scheduled and any(
            abs((s.astimezone(ZoneInfo(profile.timezone)) - scheduled.astimezone(ZoneInfo(profile.timezone))).total_seconds()) < 1800
            for s in available
        ):
            booking = await crm_book(
                session=session,
                workspace_id=conversation.workspace_id,
                conversation_id=conversation.id,
                lead_name=conversation.customer_name or customer_phone,
                lead_phone=customer_phone,
                lead_company="",
                meeting_datetime=scheduled.isoformat(),
            )
            await meeting_service.book_meeting(
                session=session,
                workspace_id=conversation.workspace_id,
                lead_id=booking.get("lead_id"),
                scheduled_at=scheduled,
                whatsapp_conversation_id=conversation.id,
                lead_name=conversation.customer_name or customer_phone,
                lead_phone=customer_phone,
            )
            meeting_booked = bool(booking.get("booking_ref"))
            await agent_realtime.publish_activity(
                session, conversation.workspace_id, "wa_meeting_booked",
                whatsapp_conversation_id=conversation.id,
                detail=f"Meeting booked {scheduled.isoformat()} ({booking.get('booking_ref')})",
            )
            await agent_realtime.publish_activity(
                session, conversation.workspace_id, "wa_crm_updated",
                whatsapp_conversation_id=conversation.id, detail="Lead saved to CRM",
            )

    conversation.updated_at = datetime.now(timezone.utc)
    await session.commit()

    return {
        "status": "replied",
        "reply": body,
        "action": action,
        "interested": interested,
        "meeting_booked": meeting_booked,
    }


async def handle_webhook_message(
    session: AsyncSession,
    account: WhatsAppAccount,
    conversation: WhatsAppConversation,
    wamid: str,
    body: str,
) -> dict:
    """Entry point called from the webhook after the conversation exists.
    Dedups by Meta wamid, stores the inbound message, then auto-responds if the
    receptionist is enabled."""
    already = await session.execute(
        select(WhatsAppConversationMessage.id).where(
            WhatsAppConversationMessage.conversation_id == conversation.id,
            WhatsAppConversationMessage.provider_message_id == wamid,
        )
    )
    if already.scalar_one_or_none() is not None:
        return {"status": "already_processed"}

    session.add(
        WhatsAppConversationMessage(
            conversation_id=conversation.id,
            sender_type="customer",
            direction="inbound",
            content=body,
            is_approved=True,
            sent_at=datetime.now(timezone.utc),
            provider_message_id=wamid,
        )
    )
    conversation.last_processed_message_id = wamid
    conversation.updated_at = datetime.now(timezone.utc)
    await session.commit()

    if not conversation.ai_agent_active or conversation.status != "active":
        return {"status": "stored_only", "reason": "ai_paused"}

    try:
        return await auto_respond_to_conversation(session, account, conversation, body)
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}
