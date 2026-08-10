import json
from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.email_account import EmailDraft, EmailConversation, EmailConversationMessage
from app.services.email_compose_service import create_draft, send_draft


EMAIL_GENERATION_PROMPT = """You are an expert B2B email copywriter for {company_name}.
Your task is to write a professional, personalized outreach email.

Company context:
- Company: {company_name}
- Services: {services}
- USP: {usp}
- Industry: {industry}

Target lead:
- Name: {lead_name}
- Company: {lead_company}
- Email: {lead_email}

Instructions:
1. Write a compelling subject line
2. Write a personalized email body (3-5 paragraphs)
3. Keep it professional but friendly
4. Include a clear call-to-action
5. Make it feel personal, not spammy

Return JSON format:
{{
    "subject": "email subject line",
    "body": "email body in HTML format"
}}"""


async def generate_email_with_ai(
    prompt: str,
    lead_name: str = "",
    lead_company: str = "",
    lead_email: str = "",
    company_name: str = "Crawlio",
    services: str = "B2B lead generation and email automation",
    usp: str = "AI-powered outreach that converts",
    industry: str = "SaaS",
) -> dict:
    if not settings.mistral_api_key:
        raise RuntimeError("MISTRAL_API_KEY is not configured")

    full_prompt = EMAIL_GENERATION_PROMPT.format(
        company_name=company_name,
        services=services,
        usp=usp,
        industry=industry,
        lead_name=lead_name,
        lead_company=lead_company,
        lead_email=lead_email,
    )

    payload = {
        "model": "mistral-small-latest",
        "messages": [
            {"role": "system", "content": full_prompt},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.7,
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


async def generate_email_draft(
    session: AsyncSession,
    workspace_id: str,
    email_account_id: str,
    prompt: str,
    lead_id: Optional[str] = None,
    lead_name: str = "",
    lead_company: str = "",
    lead_email: str = "",
) -> EmailDraft:
    result = await generate_email_with_ai(
        prompt=prompt,
        lead_name=lead_name,
        lead_company=lead_company,
        lead_email=lead_email,
    )

    draft = await create_draft(
        session=session,
        workspace_id=workspace_id,
        email_account_id=email_account_id,
        subject=result.get("subject", ""),
        body=result.get("body", ""),
        kind="ai_generated",
        recipient_emails=[lead_email] if lead_email else None,
        lead_id=lead_id,
        ai_prompt=prompt,
    )
    return draft


async def approve_and_send_ai_email(
    session: AsyncSession, draft_id: str
) -> Optional[dict]:
    result = await session.execute(select(EmailDraft).where(EmailDraft.id == draft_id))
    draft = result.scalar_one_or_none()
    if not draft or draft.kind != "ai_generated":
        return None

    email_message = await send_draft(session, draft_id)
    return {"draft_id": draft.id, "email_message_id": email_message.id if email_message else None}


async def initialize_agent_session(
    session: AsyncSession,
    workspace_id: str,
    email_account_id: str,
    lead_id: Optional[str] = None,
    subject: str = "Outreach Conversation",
    lead_name: Optional[str] = None,
    lead_email: Optional[str] = None,
) -> EmailConversation:
    if lead_email is None and lead_id:
        result = await session.execute(
            select(__import__("app.db.models.lead", fromlist=["Lead"]).Lead).where(
                __import__("app.db.models.lead", fromlist=["Lead"]).Lead.id == lead_id
            )
        )
        lead = result.scalar_one_or_none()
        if lead:
            lead_email = lead.email
            lead_name = lead_name or lead.name

    conversation = EmailConversation(
        workspace_id=workspace_id,
        email_account_id=email_account_id,
        lead_id=lead_id,
        subject=subject,
        status="active",
        ai_agent_active=True,
        customer_email=lead_email,
        customer_name=lead_name,
    )
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    return conversation


async def get_agent_conversation_history(
    session: AsyncSession, conversation_id: str
) -> list[EmailConversationMessage]:
    result = await session.execute(
        select(EmailConversationMessage)
        .where(EmailConversationMessage.conversation_id == conversation_id)
        .order_by(EmailConversationMessage.created_at)
    )
    return list(result.scalars().all())


async def agent_collect_business_info(
    session: AsyncSession, conversation_id: str, user_input: str
) -> str:
    conversation_result = await session.execute(
        select(EmailConversation).where(EmailConversation.id == conversation_id)
    )
    conversation = conversation_result.scalar_one_or_none()
    if not conversation:
        raise RuntimeError("Conversation not found")

    user_msg = EmailConversationMessage(
        conversation_id=conversation_id,
        sender_type="user",
        content=user_input,
    )
    session.add(user_msg)

    existing_context = conversation.business_context or ""
    conversation.business_context = f"{existing_context}\nUser: {user_input}".strip()
    conversation.updated_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)

    ai_response = f"Samajh gaya! Maine ye note kar liya hai: {user_input}. Koi aur detail hai jo aap share karna chahenge?"

    ai_msg = EmailConversationMessage(
        conversation_id=conversation_id,
        sender_type="ai",
        content=ai_response,
    )
    session.add(ai_msg)
    await session.commit()
    return ai_response


async def agent_generate_outreach(
    session: AsyncSession, conversation_id: str
) -> EmailDraft:
    conv_result = await session.execute(
        select(EmailConversation).where(EmailConversation.id == conversation_id)
    )
    conversation = conv_result.scalar_one_or_none()
    if not conversation:
        raise RuntimeError("Conversation not found")

    business_context = conversation.business_context or "No business context provided"

    ai_result = await generate_email_with_ai(
        prompt=f"Generate outreach email based on this business context: {business_context}",
        company_name="Crawlio",
        services="B2B lead generation",
        usp="AI-powered outreach",
    )

    draft = await create_draft(
        session=session,
        workspace_id=conversation.workspace_id,
        email_account_id=conversation.email_account_id,
        subject=ai_result.get("subject", ""),
        body=ai_result.get("body", ""),
        kind="ai_generated",
        lead_id=conversation.lead_id,
        ai_prompt=business_context,
        conversation_id=conversation_id,
    )

    preview_msg = EmailConversationMessage(
        conversation_id=conversation_id,
        sender_type="ai",
        content=f"Maine outreach email generate kar diya hai. Subject: {draft.subject}",
    )
    session.add(preview_msg)
    await session.commit()

    return draft


async def agent_stop_conversation(
    session: AsyncSession, conversation_id: str
) -> bool:
    result = await session.execute(
        select(EmailConversation).where(EmailConversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        return False

    conversation.ai_agent_active = False
    conversation.status = "paused"
    conversation.updated_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    await session.commit()
    return True


async def agent_resume_conversation(
    session: AsyncSession, conversation_id: str
) -> bool:
    result = await session.execute(
        select(EmailConversation).where(EmailConversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        return False

    conversation.ai_agent_active = True
    conversation.status = "active"
    conversation.updated_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    await session.commit()
    return True


AUTO_REPLY_PROMPT = """You are the AI email agent for {company_name}, an AI receptionist that handles customer replies professionally.

Business context:
{business_context}

Conversation history so far (oldest to newest):
{history}

The customer's latest reply:
Customer: {incoming_message}

Available meeting slots (UTC ISO datetimes, choose ONLY from these or suggest one from these):
{available_slots}

Instructions:
1. Respond to the customer's latest reply in a natural, helpful tone.
2. Keep the reply short and professional (2-4 sentences).
3. If the customer explicitly asks to unsubscribe / stop emails / opt out, set action to "unsubscribe" and confirm politely and briefly.
4. If the customer wants a meeting, pick the earliest suitable slot from the available list and confirm it clearly (action "book").
5. If unsure, action is "reply".

Return JSON format:
{{
    "action": "reply" | "unsubscribe" | "book",
    "subject": "email subject line (Re: ...)",
    "body": "reply body in plain text (no HTML)",
    "interested": true/false,
    "selected_slot": "UTC ISO datetime from the available list (or null)"
}}"""


async def _run_auto_reply_llm(
    business_context: str,
    history: str,
    incoming_message: str,
    company_name: str = "Crawlio",
    available_slots: Optional[list[str]] = None,
) -> dict:
    slots_text = "\n".join(f"  {s}" for s in (available_slots or [])) or "  (none available right now)"
    full_prompt = AUTO_REPLY_PROMPT.format(
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
        "temperature": 0.6,
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


def _extract_from_email(raw_from: str) -> str:
    """Extract a bare email address from a Gmail 'Name <a@b.c>' header."""
    if not raw_from:
        return ""
    if "<" in raw_from and ">" in raw_from:
        return raw_from.split("<")[1].split(">")[0].strip()
    return raw_from.strip()


UNSUBSCRIBE_KEYWORDS = (
    "unsubscribe", "remove me", "stop emailing", "stop emailing me",
    "don't contact me", "do not contact me", "opt out", "not interested in emails",
    "stop sending me", "remove me from your list", "take me off",
)


def _is_unsubscribe_message(message: str) -> bool:
    lowered = (message or "").lower()
    return any(word in lowered for word in UNSUBSCRIBE_KEYWORDS)


async def auto_respond_to_conversation(
    session: AsyncSession,
    conversation: EmailConversation,
    incoming_message: str,
) -> dict:
    """Generate + send an AI reply for a customer's inbound email, log it in the
    conversation, and auto-book a meeting (from REAL available slots) + hot-lead
    the customer if interested. Every stage is persisted as AIActivity and
    pushed to the workspace's WebSocket channel in real time."""
    from app.services import email_sync_service, meeting_service, agent_realtime
    from app.services.business_profile_service import get_profile, to_context
    from app.db.models.email_account import EmailAccount
    from datetime import datetime, timezone

    await agent_realtime.publish_activity(
        session, conversation.workspace_id, "email_received",
        conversation_id=conversation.id, detail="New inbound email received",
    )

    # STOP guard #1: never process a conversation the owner has paused.
    if not conversation.ai_agent_active or conversation.status != "active":
        return {"status": "skipped", "reason": "ai_paused"}

    account_result = await session.execute(
        select(EmailAccount).where(EmailAccount.id == conversation.email_account_id)
    )
    account = account_result.scalar_one_or_none()
    if not account:
        raise RuntimeError("Email account not found")

    recipient = conversation.customer_email or _extract_from_email(incoming_message)
    if not recipient:
        raise RuntimeError("No customer email to reply to")

    profile = await get_profile(session, conversation.workspace_id)
    business_context = conversation.business_context or ""
    if profile:
        business_context = f"{to_context(profile, account.email_address)}\n\nAgent notes:\n{business_context}"

    await agent_realtime.publish_activity(
        session, conversation.workspace_id, "lead_identified",
        conversation_id=conversation.id, detail=f"Identified lead {recipient}",
    )

    messages = await get_agent_conversation_history(session, conversation.id)
    history_lines = [f"{m.sender_type.upper()}: {m.content}" for m in messages]
    history = "\n".join(history_lines)

    # Real availability: slots derived from business hours + booked meetings.
    available = []
    if profile:
        booked = await meeting_service.list_bookable_meetings(session, conversation.workspace_id)
        available = meeting_service.next_slots(profile, count=4, bookable=booked)
    available_text = [s.isoformat() for s in available]

    await agent_realtime.publish_activity(
        session, conversation.workspace_id, "intent_detected",
        conversation_id=conversation.id, detail="Reading conversation + intent",
    )

    if _is_unsubscribe_message(incoming_message):
        result = {"action": "unsubscribe"}

        await agent_realtime.publish_activity(
            session, conversation.workspace_id, "unsubscribe_detected",
            conversation_id=conversation.id, detail="Customer opted out",
        )
    else:
        result = await _run_auto_reply_llm(
            business_context=business_context,
            history=history,
            incoming_message=incoming_message,
            company_name=profile.business_name if profile else "Crawlio",
            available_slots=available_text,
        )

    action = result.get("action") or ("reply" if not _is_unsubscribe_message(incoming_message) else "unsubscribe")
    subject = result.get("subject", f"Re: {conversation.subject}")
    if "Re:" not in subject:
        subject = f"Re: {conversation.subject}"
    body = result.get("body", "")
    interested = bool(result.get("interested"))

    # STOP guard #2: only send if the agent is still enabled right now.
    if not conversation.ai_agent_active or conversation.status != "active":
        await agent_realtime.publish_activity(
            session, conversation.workspace_id, "ai_stopped",
            conversation_id=conversation.id, status="failed", detail="Agent stopped before send",
        )
        return {"status": "skipped", "reason": "ai_paused_before_send"}

    if action == "unsubscribe":
        from app.db.models.lead import Lead
        from sqlalchemy import or_ as sa_or

        lead_result = await session.execute(
            select(Lead).where(
                Lead.workspace_id == conversation.workspace_id,
                sa_or(Lead.email == recipient, Lead.id == (conversation.lead_id or "")),
            )
        )
        lead = lead_result.scalars().first()
        if lead is not None:
            lead.unsubscribed_at = datetime.now(timezone.utc)
            lead.status = "Unsubscribed"
            lead.updated_at = datetime.now(timezone.utc)
        if not body:
            body = "Understood. You have been removed from our outreach list and will not receive further emails from us."

    await email_sync_service.send_email_from_account(session, account, recipient, subject, body)

    await agent_realtime.publish_activity(
        session, conversation.workspace_id, "ai_reply_sent",
        conversation_id=conversation.id, detail="Reply sent to customer",
    )

    customer_msg = EmailConversationMessage(
        conversation_id=conversation.id,
        sender_type="customer",
        content=incoming_message,
        is_approved=True,
        sent_at=datetime.now(timezone.utc),
    )
    session.add(customer_msg)

    ai_msg = EmailConversationMessage(
        conversation_id=conversation.id,
        sender_type="ai",
        content=body,
        is_approved=True,
        sent_at=datetime.now(timezone.utc),
    )
    session.add(ai_msg)

    meeting_booked = False
    if action == "book" and interested and profile:
        from app.services.email_conversation_service import book_meeting as crm_book
        import uuid as _uuid
        from zoneinfo import ZoneInfo

        selected_slot = result.get("selected_slot")
        if selected_slot:
            try:
                scheduled = datetime.fromisoformat(selected_slot)
                if scheduled.tzinfo is None:
                    scheduled = scheduled.replace(tzinfo=ZoneInfo(profile.timezone))
            except ValueError:
                scheduled = None
            # Only ever book a slot that was actually offered.
            if scheduled and any(abs((s.astimezone(ZoneInfo(profile.timezone)) - scheduled.astimezone(ZoneInfo(profile.timezone))).total_seconds()) < 1800 for s in available):
                booking = await crm_book(
                    session=session,
                    workspace_id=conversation.workspace_id,
                    conversation_id=conversation.id,
                    lead_name=conversation.customer_name or recipient,
                    lead_email=recipient,
                    lead_company="",
                    meeting_datetime=scheduled.isoformat(),
                )
                await meeting_service.book_meeting(
                    session=session,
                    workspace_id=conversation.workspace_id,
                    lead_id=booking.get("lead_id"),
                    scheduled_at=scheduled,
                    conversation_id=conversation.id,
                    lead_name=conversation.customer_name or recipient,
                    lead_email=recipient,
                )
                meeting_booked = bool(booking.get("booking_ref"))
                await agent_realtime.publish_activity(
                    session, conversation.workspace_id, "meeting_booked",
                    conversation_id=conversation.id,
                    detail=f"Meeting booked {scheduled.isoformat()} ({booking.get('booking_ref')})",
                )
                await agent_realtime.publish_activity(
                    session, conversation.workspace_id, "crm_updated",
                    conversation_id=conversation.id, detail="Lead saved to CRM",
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


async def process_inbound_replies_for_account(
    session: AsyncSession, account_id: str
) -> dict:
    """Sync-based auto-agent: fetch inbox, match customer replies to active AI
    conversations, and auto-respond to each new one (deduped by message id)."""
    from app.services import email_sync_service
    from app.db.models.email_account import EmailAccount

    account_result = await session.execute(
        select(EmailAccount).where(EmailAccount.id == account_id)
    )
    account = account_result.scalar_one_or_none()
    if not account:
        raise RuntimeError("Email account not found")

    inbox = await email_sync_service.sync_inbox(session, account)

    conv_result = await session.execute(
        select(EmailConversation).where(
            EmailConversation.email_account_id == account_id,
            EmailConversation.ai_agent_active == True,  # noqa: E712
            EmailConversation.status == "active",
        )
    )
    conversations = list(conv_result.scalars().all())

    replied: list[dict] = []
    for conv in conversations:
        if not conv.customer_email:
            continue

        new_messages = [
            m for m in inbox
            if _extract_from_email(m.get("from", "")).lower() == conv.customer_email.lower()
            and m.get("id") != conv.last_processed_message_id
        ]
        if not new_messages:
            continue

        latest = new_messages[0]
        detail = await email_sync_service.get_email_detail(session, account, latest["id"])
        incoming_body = detail.get("body") or detail.get("snippet") or ""

        try:
            result = await auto_respond_to_conversation(
                session, conv, incoming_body
            )
        except Exception as exc:
            result = {"status": "failed", "error": str(exc)}

        conv.last_processed_message_id = latest["id"]
        conv.updated_at = datetime.now(timezone.utc)
        await session.commit()

        replied.append({"conversation_id": conv.id, "result": result})

    return {"processed": len(replied), "results": replied}
