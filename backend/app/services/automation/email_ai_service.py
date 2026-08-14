import json
from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.integration_runtime import api_key
from app.db.models.email_account import EmailDraft, EmailConversation, EmailConversationMessage
from app.db.models.lead import Lead
from app.services.automation.email_compose_service import create_draft, send_draft
from app.services.automation.email_conversation_service import _extract_email



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
    company_name: str = "our business",
    services: str = "",
    usp: str = "",
    industry: str = "",
) -> dict:
    if not api_key("mistral_api_key"):
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
                "Authorization": f"Bearer {api_key('mistral_api_key')}",
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
            select(Lead).where(Lead.id == lead_id)
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
    from sqlalchemy import func as sa_func
    from app.services.automation.email_conversation_service import clean_message_content


    result = await session.execute(
        select(EmailConversationMessage)
        .where(EmailConversationMessage.conversation_id == conversation_id)
        .order_by(sa_func.coalesce(EmailConversationMessage.sent_at, EmailConversationMessage.created_at))
    )
    messages = list(result.scalars().all())
    for msg in messages:
        msg.content = clean_message_content(msg.content)
    return messages


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
    conversation.updated_at = datetime.now(timezone.utc)

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

    from app.services.agent.business_profile_service import get_profile


    profile = await get_profile(session, conversation.workspace_id)
    ai_result = await generate_email_with_ai(
        prompt=f"Generate outreach email based on this business context: {business_context}",
        company_name=(profile.business_name if profile and profile.business_name else "our business"),
        services=(profile.services or "") if profile else "",
        usp=(profile.usp or "") if profile else "",
        industry=(profile.industry or "") if profile else "",
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


AUTO_REPLY_PROMPT = """You are the AI receptionist for {company_name}, a friendly, professional receptionist answering customer emails on behalf of that business.

You are NOT a platform or software product. Always write as a person working for {company_name}. Never mention Crawlio, AI agents, receptionist software, or that you are an automated system unless the business context explicitly instructs you to.

Business context:
{business_context}

Conversation history so far (oldest to newest):
{history}

The customer's latest reply:
Customer: {incoming_message}

Available meeting slots (UTC ISO datetimes, choose ONLY from these or suggest one from these):
{available_slots}

Instructions:
1. Respond to the customer's latest reply in a natural, helpful tone as a receptionist of {company_name}.
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


AUTO_REPLY_PROMPT_BOOKED = """You are the AI receptionist for {company_name}, a friendly, professional receptionist answering customer emails on behalf of that business.

You are NOT a platform or software product. Always write as a person working for {company_name}. Never mention Crawlio, AI agents, receptionist software, or that you are an automated system unless the business context explicitly instructs you to.

This customer has ALREADY booked a meeting with {company_name}.

Business context:
{business_context}

Conversation history so far (oldest to newest):
{history}

The customer's latest reply:
Customer: {incoming_message}

Available meeting slots for rebooking (UTC ISO datetimes, choose ONLY from these or suggest one from these):
{available_slots}

Instructions:
1. Stay warm and professional; the lead already has a booking with {company_name}.
2. If the customer wants to RESCHEDULE or book ANOTHER meeting → action "rebook", pick the earliest suitable slot from the list and confirm it clearly.
3. If the customer is giving FEEDBACK or asking service/business questions → answer helpfully, thank them, and invite more feedback → action "reply".
4. For any other message → reply helpfully in 2-4 sentences → action "reply".
5. If the customer explicitly asks to unsubscribe / stop emails / opt out → action "unsubscribe" and confirm politely and briefly.

Return JSON format:
{{
    "action": "rebook" | "reply" | "unsubscribe",
    "subject": "email subject line (Re: ...)",
    "body": "reply body in plain text (no HTML)",
    "interested": true/false,
    "selected_slot": "UTC ISO datetime from the available list (or null)"
}}"""


async def _run_auto_reply_llm(
    business_context: str,
    history: str,
    incoming_message: str,
    company_name: str = "our team",
    available_slots: Optional[list[str]] = None,
    booked: bool = False,
) -> dict:
    slots_text = "\n".join(f"  {s}" for s in (available_slots or [])) or "  (none available right now)"
    template = AUTO_REPLY_PROMPT_BOOKED if booked else AUTO_REPLY_PROMPT
    full_prompt = template.format(
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
                "Authorization": f"Bearer {api_key('mistral_api_key')}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

    content = data["choices"][0]["message"]["content"]
    return json.loads(content)


UNSUBSCRIBE_KEYWORDS = (
    "unsubscribe", "remove me", "stop emailing", "stop emailing me",
    "don't contact me", "do not contact me", "opt out", "not interested in emails",
    "stop sending me", "remove me from your list", "take me off",
)


def _is_unsubscribe_message(message: str) -> bool:
    lowered = (message or "").lower()
    return any(word in lowered for word in UNSUBSCRIBE_KEYWORDS)


async def _is_lead_booked(
    session: AsyncSession,
    workspace_id: str,
    conversation_id: str,
    recipient: Optional[str] = None,
) -> bool:
    """True when this customer is already booked.

    Checks BOTH (1) a booked Meeting row for the customer's email in this
    workspace, and (2) the "Meeting booked!..." system message fallback on
    this conversation. A split conversation history for the same customer
    therefore still triggers the booked flow correctly."""
    from sqlalchemy import func as sa_func
    from app.db.models.agent import Meeting

    if recipient:
        result = await session.execute(
            select(Meeting.id)
            .where(
                Meeting.workspace_id == workspace_id,
                Meeting.status == "booked",
                sa_func.lower(Meeting.lead_email) == recipient.lower(),
            )
            .limit(1)
        )
        if result.first() is not None:
            return True

    result = await session.execute(
        select(EmailConversationMessage.id)
        .where(
            EmailConversationMessage.conversation_id == conversation_id,
            EmailConversationMessage.sender_type == "system",
            EmailConversationMessage.content.like("Meeting booked!%"),
        )
        .limit(1)
    )
    return result.first() is not None


async def auto_respond_to_conversation(
    session: AsyncSession,
    conversation: EmailConversation,
    incoming_message: str,
) -> dict:
    """Generate + send an AI reply for a customer's inbound email, log it in the
    conversation, and auto-book a meeting (from REAL available slots) + hot-lead
    the customer if interested. Every stage is persisted as AIActivity and
    pushed to the workspace's WebSocket channel in real time."""
    from app.services.agent import agent_realtime
    from app.services.automation import email_sync_service, meeting_service
    from app.services.agent.business_profile_service import get_profile, to_context

    from app.services.automation.email_conversation_service import clean_message_content

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
    is_booked = await _is_lead_booked(
        session, conversation.workspace_id, conversation.id, recipient
    )

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
    subject = result.get("subject", f"Re: {conversation.subject}")
    if "Re:" not in subject:
        subject = f"Re: {conversation.subject}"
    body = clean_message_content(result.get("body", ""))
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

    send_result = await email_sync_service.send_email_from_account(
        session, account, recipient, subject, body, thread_id=conversation.thread_id
    )
    outbound_id = None
    if send_result:
        outbound_id = (
            send_result.get("id")
            or send_result.get("messageId")
            or send_result.get("email_message_id")
        )

    await agent_realtime.publish_activity(
        session, conversation.workspace_id, "ai_reply_sent",
        conversation_id=conversation.id, detail="Reply sent to customer",
    )

    ai_msg = EmailConversationMessage(
        conversation_id=conversation.id,
        sender_type="ai",
        direction="outbound",
        content=body,
        is_approved=True,
        sent_at=datetime.now(timezone.utc),
        provider_message_id=outbound_id,
    )
    session.add(ai_msg)

    meeting_booked = False
    if action in ("book", "rebook") and interested and profile:
        from app.services.automation.email_conversation_service import book_meeting as crm_book

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


async def _is_inbound_processed(
    session: AsyncSession, account_id: str, provider_message_id: str
) -> bool:
    """Idempotency guard: a provider message must never be processed twice."""
    if not provider_message_id:
        return False
    result = await session.execute(
        select(EmailConversationMessage.id)
        .join(EmailConversation, EmailConversation.id == EmailConversationMessage.conversation_id)
        .where(
            EmailConversation.email_account_id == account_id,
            EmailConversationMessage.provider_message_id == provider_message_id,
        )
    )
    return result.first() is not None


async def _store_inbound_message(
    session: AsyncSession,
    conversation: EmailConversation,
    message_id: str,
    content: str,
) -> bool:
    """Append the customer's inbound email to the conversation. Returns True if
    newly stored, False if it was already processed (dedup)."""
    already = await session.execute(
        select(EmailConversationMessage.id).where(
            EmailConversationMessage.conversation_id == conversation.id,
            EmailConversationMessage.provider_message_id == message_id,
        )
    )
    if already.scalar_one_or_none() is not None:
        return False

    session.add(
        EmailConversationMessage(
            conversation_id=conversation.id,
            sender_type="customer",
            direction="inbound",
            content=content,
            is_approved=True,
            sent_at=datetime.now(timezone.utc),
            provider_message_id=message_id,
        )
    )
    conversation.last_processed_message_id = message_id
    conversation.updated_at = datetime.now(timezone.utc)
    await session.commit()
    return True


inbound_scan_guard: dict[str, datetime] = {}


async def process_inbound_replies_for_account(
    session: AsyncSession, account_id: str
) -> dict:
    """Core auto-receptionist pipeline.

    For EVERY new inbound email from a customer:
      1. identify the customer (from address, never the account itself)
      2. find-or-create ONE stable conversation per customer
      3. append the inbound message to that conversation (dedup by message id)
      4. if the receptionist is enabled for the conversation, generate a reply
         from business knowledge + full conversation history + the new message,
         send it for real through the connected Gmail account (same thread),
         and append the outbound message to the same conversation.
    """
    from app.services.automation import email_sync_service
    from app.services.automation.email_conversation_service import _extract_name, clean_message_content, find_or_create_conversation, strip_email_quotes

    from app.db.models.email_account import EmailAccount

    # Cooldown: don't re-scan the same mailbox back-to-back (it hammers Gmail).
    now = datetime.now(timezone.utc)
    last = inbound_scan_guard.get(account_id)
    if last and (now - last).total_seconds() < 25:
        return {"processed": 0, "results": [], "reason": "cooldown"}
    inbound_scan_guard[account_id] = now

    account_result = await session.execute(
        select(EmailAccount).where(EmailAccount.id == account_id)
    )
    account = account_result.scalar_one_or_none()
    if not account:
        raise RuntimeError("Email account not found")

    try:
        inbox, _ = await email_sync_service.sync_inbox(session, account, page=1, page_size=20, max_total=20)
    except Exception as exc:
        # Gmail token refresh / IMAP / auth errors must surface as a clean
        # signal, never as a masked 500 — the frontend turns these into a
        # "reconnect your Gmail" prompt.
        msg = str(exc).lower()
        is_auth = (
            "invalid_grant" in msg
            or "unauthorized" in msg
            or "401" in msg
            or "token" in msg
            or "oauth" in msg
            or isinstance(exc, RuntimeError)
        )
        return {
            "processed": 0,
            "results": [],
            "error": str(exc),
            "reconnect_required": bool(is_auth),
            "reason": "gmail_sync_failed",
        }

    account_email = (account.email_address or "").lower()
    processed: list[dict] = []
    for msg in inbox:
        from_addr = _extract_from_email(msg.get("from", ""))
        if not from_addr or from_addr.lower() == account_email:
            # Loop protection: never respond to our own outgoing mail.
            continue
        if await _is_inbound_processed(session, account_id, msg.get("id", "")):
            continue

        try:
            conversation = await find_or_create_conversation(
                session,
                workspace_id=account.workspace_id,
                email_account_id=account_id,
                customer_email=from_addr,
                customer_name=_extract_name(msg.get("from", "")),
                subject=msg.get("subject", ""),
                thread_id=msg.get("thread_id"),
                message_id=msg.get("id"),
                ai_enabled=True,
            )
        except RuntimeError as exc:
            processed.append({"message_id": msg.get("id"), "result": {"status": "failed", "error": str(exc)}})
            continue

        detail = await email_sync_service.get_email_detail(session, account, msg["id"])
        incoming_body = strip_email_quotes(detail.get("body") or detail.get("snippet") or "")

        stored = await _store_inbound_message(
            session, conversation, msg.get("id", ""), incoming_body or msg.get("snippet", "")
        )
        if not stored:
            continue

        if not conversation.ai_agent_active or conversation.status != "active":
            # Receptionist stopped for this conversation: log only, no reply.
            processed.append({
                "conversation_id": conversation.id,
                "result": {"status": "stored_only", "reason": "ai_paused"},
            })
            continue

        try:
            result = await auto_respond_to_conversation(
                session, conversation, incoming_body
            )
        except Exception as exc:
            result = {"status": "failed", "error": str(exc)}

        processed.append({"conversation_id": conversation.id, "result": result})

    return {"processed": len(processed), "results": processed}
