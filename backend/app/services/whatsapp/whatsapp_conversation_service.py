"""WhatsApp conversation service: find-or-create by phone, inbox previews,
manual reply, booking (CRM save), CSV export. Mirrors email_conversation_service
but keys conversations by customer PHONE number instead of email."""

import csv
import io
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.whatsapp import (
    WhatsAppAccount,
    WhatsAppConversation,
    WhatsAppConversationMessage,
)
from app.services.whatsapp import whatsapp_service


def _collapse_ws(text: str) -> str:
    """Trim whitespace per line and collapse runs of blank lines to one."""
    out: list[str] = []
    blanks = 0
    for line in (text or "").splitlines():
        line = line.replace("\xa0", " ").replace("\r", "").strip()
        if not line:
            blanks += 1
            if blanks <= 1:
                out.append("")
            continue
        blanks = 0
        out.append(line)
    return "\n".join(out).strip()


def clean_message_content(text: str) -> str:
    """Normalize a WhatsApp message into clean plain chat text (WhatsApp bodies
    are already plain; this just collapses whitespace + strips any HTML that may
    have leaked in)."""
    if not text:
        return ""
    import html as html_module
    t = re.sub(r"<[^>]+>", "", text)
    t = html_module.unescape(t)
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)
    t = re.sub(r"`(?!#)([^`]+?)`", r"\1", t)
    return _collapse_ws(t)


def format_phone(raw: Optional[str]) -> str:
    """Display-form phone: keep the leading + and readable grouping."""
    if not raw:
        return ""
    return whatsapp_service.normalize_phone(raw)


async def find_or_create_conversation(
    session: AsyncSession,
    workspace_id: str,
    whatsapp_account_id: str,
    customer_phone: str,
    customer_name: str = "",
    ai_enabled: bool = True,
) -> WhatsAppConversation:
    """Return the single stable conversation for (account, customer_phone).

    One customer phone = ONE continuous conversation (same rule as email)."""
    customer_phone = format_phone(customer_phone)
    if not customer_phone:
        raise RuntimeError("No customer phone to identify the conversation")

    result = await session.execute(
        select(WhatsAppConversation)
        .where(
            WhatsAppConversation.whatsapp_account_id == whatsapp_account_id,
            WhatsAppConversation.customer_phone.isnot(None),
            WhatsAppConversation.customer_phone == customer_phone,
        )
        .order_by(WhatsAppConversation.created_at.asc())
    )
    existing = list(result.scalars().all())
    if existing:
        conv = existing[0]
        if customer_name and not conv.customer_name:
            conv.customer_name = customer_name
            conv.updated_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(conv)
        return conv

    conv = WhatsAppConversation(
        workspace_id=workspace_id,
        whatsapp_account_id=whatsapp_account_id,
        lead_id=None,
        status="active",
        ai_agent_active=ai_enabled,
        customer_phone=customer_phone,
        customer_name=customer_name or None,
    )
    session.add(conv)
    await session.commit()
    await session.refresh(conv)
    return conv


async def get_conversation(
    session: AsyncSession, conversation_id: str
) -> Optional[WhatsAppConversation]:
    result = await session.execute(
        select(WhatsAppConversation).where(WhatsAppConversation.id == conversation_id)
    )
    return result.scalar_one_or_none()


async def send_conversation_message(
    session: AsyncSession,
    conversation_id: str,
    message: str,
    sender_type: str = "user",
) -> WhatsAppConversationMessage:
    msg = WhatsAppConversationMessage(
        conversation_id=conversation_id,
        sender_type=sender_type,
        content=message,
    )
    session.add(msg)
    await session.commit()
    await session.refresh(msg)
    return msg


async def send_reply_message(
    session: AsyncSession,
    conversation_id: str,
    message: str,
    sender_type: str = "user",
) -> dict:
    """Manually reply to the customer: send a real WhatsApp message + log it.

    Uses the account's connected phone_number_id. If the message can't be sent
    (e.g. 24h window closed) it still logs the outbound row so the user sees it;
    the caller decides whether to surface the error."""
    conv = await get_conversation(session, conversation_id)
    if not conv:
        raise RuntimeError("Conversation not found")

    account_result = await session.execute(
        select(WhatsAppAccount).where(WhatsAppAccount.id == conv.whatsapp_account_id)
    )
    account = account_result.scalar_one_or_none()
    if not account:
        raise RuntimeError("WhatsApp account not found")
    if not (account.access_token and account.phone_number_id):
        raise RuntimeError("WhatsApp account not connected")

    customer_phone = conv.customer_phone
    if not customer_phone:
        raise RuntimeError("No customer phone on this conversation")

    outbound_id = None
    try:
        send_result = await whatsapp_service.send_text_message(
            account.access_token,
            account.phone_number_id,
            customer_phone,
            message,
        )
        outbound_id = whatsapp_service.extract_wamid(send_result)
    except Exception:
        # Log the attempt anyway; caller surfaces the 24h-window error.
        outbound_id = None

    msg = WhatsAppConversationMessage(
        conversation_id=conversation_id,
        sender_type=sender_type,
        direction="outbound",
        content=message,
        is_approved=True,
        sent_at=datetime.now(timezone.utc),
        provider_message_id=outbound_id,
    )
    session.add(msg)
    conv.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(msg)
    return {"status": "sent", "message": msg.content, "provider_message_id": outbound_id}


async def stop_conversation(
    session: AsyncSession, conversation_id: str
) -> bool:
    conv = await get_conversation(session, conversation_id)
    if not conv:
        return False
    conv.ai_agent_active = False
    conv.status = "paused"
    conv.updated_at = datetime.now(timezone.utc)
    await session.commit()
    return True


async def resume_conversation(
    session: AsyncSession, conversation_id: str
) -> bool:
    conv = await get_conversation(session, conversation_id)
    if not conv:
        return False
    conv.ai_agent_active = True
    conv.status = "active"
    conv.updated_at = datetime.now(timezone.utc)
    await session.commit()
    return True


async def save_business_info(
    session: AsyncSession,
    conversation_id: str,
    business_name: str,
    business_subject: str,
    business_additional_info: str = "",
) -> dict:
    """Persist the customer/agent's remembered info onto the conversation so the
    agent never asks for it again (the 'info once' requirement). Stored as JSON
    text in business_context."""
    import json

    conv = await get_conversation(session, conversation_id)
    if not conv:
        raise RuntimeError("Conversation not found")

    context = {"business_name": business_name, "business_subject": business_subject}
    if business_additional_info:
        context["business_additional_info"] = business_additional_info

    existing = {}
    if conv.business_context:
        try:
            existing = json.loads(conv.business_context)
        except (ValueError, TypeError):
            existing = {"notes": conv.business_context}

    merged = {**existing, **context}
    conv.business_context = json.dumps(merged)
    conv.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(conv)
    return {"status": "saved", "business_context": conv.business_context}


async def book_meeting(
    session: AsyncSession,
    workspace_id: str,
    conversation_id: Optional[str],
    lead_name: str,
    lead_phone: str,
    lead_company: str,
    meeting_datetime: str,
) -> dict:
    from app.db.models.lead import Lead
    from app.db.models.crm import CrmEntry
    import sqlalchemy as sa

    # Upsert the lead by PHONE (WhatsApp's key) and promote to Hot.
    lead_result = await session.execute(
        select(Lead).where(
            sa.and_(
                Lead.workspace_id == workspace_id,
                sa.func.lower(Lead.phone) == sa.func.lower(lead_phone),
            )
        )
    )
    lead = lead_result.scalar_one_or_none()

    if lead is None:
        lead = Lead(
            workspace_id=workspace_id,
            name=lead_name or lead_phone or "Unknown lead",
            phone=lead_phone or None,
            company=lead_company or None,
            source="whatsapp_agent",
            status="Hot",
        )
        session.add(lead)
        await session.flush()
    else:
        lead.status = "Hot"
        lead.updated_at = datetime.now(timezone.utc)
        if lead_company and not lead.company:
            lead.company = lead_company

    existing_crm = await session.execute(
        select(CrmEntry).where(
            CrmEntry.workspace_id == workspace_id,
            CrmEntry.lead_id == lead.id,
        )
    )
    if existing_crm.scalar_one_or_none() is None:
        session.add(
            CrmEntry(
                workspace_id=workspace_id,
                lead_id=lead.id,
                category="with_website" if lead.website else "no_website",
            )
        )

    booking_ref = f"BKG-{uuid.uuid4().hex[:8].upper()}"

    conversation = None
    if conversation_id:
        conversation = await get_conversation(session, conversation_id)

    if conversation:
        session.add(
            WhatsAppConversationMessage(
                conversation_id=conversation.id,
                sender_type="system",
                content=f"Meeting booked! Reference: {booking_ref}. Date: {meeting_datetime}. Lead: {lead_name}.",
            )
        )

    await session.commit()

    return {
        "booking_ref": booking_ref,
        "lead_name": lead_name,
        "lead_phone": lead_phone,
        "lead_company": lead_company,
        "meeting_datetime": meeting_datetime,
        "lead_id": lead.id,
    }


async def export_booked_leads_csv(
    session: AsyncSession, workspace_id: str
) -> str:
    import sqlalchemy as sa

    result = await session.execute(
        sa.text("""
            SELECT m.content, m.created_at
            FROM whatsapp_conversation_messages m
            JOIN whatsapp_conversations c ON m.conversation_id = c.id
            WHERE c.workspace_id = :ws AND m.sender_type = 'system'
              AND m.content LIKE 'Meeting booked!%'
            ORDER BY m.created_at DESC
        """),
        {"ws": workspace_id}
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Booking Ref", "Lead Name", "Lead Phone", "Company", "Meeting Date", "Created At"])

    for row in result.fetchall():
        content = row[0]
        created_at = row[1]
        parts = {}
        for item in content.split(". "):
            if ":" in item:
                key, val = item.split(":", 1)
                parts[key.strip()] = val.strip()

        writer.writerow([
            parts.get("Reference", ""),
            parts.get("Lead", ""),
            parts.get("Phone", parts.get("Lead", "")),
            parts.get("Company", ""),
            parts.get("Date", ""),
            _csv_dt(created_at),
        ])

    return output.getvalue()


def _csv_dt(raw) -> str:
    """Format a datetime that may come back as str on SQLite raw queries."""
    if not raw:
        return ""
    if isinstance(raw, str):
        return raw[:19].replace("T", " ")
    try:
        return raw.strftime("%Y-%m-%d %H:%M:%S")
    except AttributeError:
        return str(raw)[:19]


async def get_active_conversations(
    session: AsyncSession, workspace_id: str, account_id: str
) -> list[WhatsAppConversation]:
    result = await session.execute(
        select(WhatsAppConversation)
        .where(
            WhatsAppConversation.workspace_id == workspace_id,
            WhatsAppConversation.whatsapp_account_id == account_id,
        )
        .order_by(WhatsAppConversation.updated_at.desc())
    )
    return list(result.scalars().all())


async def list_conversation_previews(
    session: AsyncSession, account_id: str, page: int = 1, page_size: int = 10
) -> tuple[list[dict], int, bool]:
    """WhatsApp-style Inbox preview: ONE row per customer (conversation),
    showing only the latest message + timestamp, ordered by latest message time."""
    conv_result = await session.execute(
        select(WhatsAppConversation)
        .where(WhatsAppConversation.whatsapp_account_id == account_id)
        .order_by(WhatsAppConversation.updated_at.desc())
    )
    all_convs = list(conv_result.scalars().all())
    total = len(all_convs)

    booked_ids = set(
        (await session.execute(
            select(WhatsAppConversationMessage.conversation_id)
            .where(
                WhatsAppConversationMessage.sender_type == "system",
                WhatsAppConversationMessage.content.like("Meeting booked!%"),
            )
        )).scalars().all()
    )

    start = (page - 1) * page_size
    page_convs = all_convs[start:start + page_size]

    items: list[dict] = []
    for conv in page_convs:
        msg_result = await session.execute(
            select(WhatsAppConversationMessage)
            .where(WhatsAppConversationMessage.conversation_id == conv.id)
            .order_by(sa_func.coalesce(WhatsAppConversationMessage.sent_at, WhatsAppConversationMessage.created_at))
        )
        msgs = list(msg_result.scalars().all())
        last = msgs[-1] if msgs else None
        items.append({
            "id": conv.id,
            "customer_name": conv.customer_name or conv.customer_phone,
            "customer_phone": conv.customer_phone,
            "last_message": clean_message_content(last.content) if last else "",
            "last_message_sender_type": last.sender_type if last else "",
            "last_message_at": (last.sent_at or last.created_at) if last else conv.updated_at,
            "ai_agent_active": conv.ai_agent_active,
            "status": conv.status,
            "is_booked": conv.id in booked_ids,
            "business_context": conv.business_context or "",
        })

    return items, total, (start + page_size) < total