import html as html_module
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.email_account import EmailAccount, EmailConversation, EmailConversationMessage, EmailDraft, DailyEmailQuota
from app.services import email_account_service


def _extract_email(raw: str) -> str:
    """Extract a bare email address from a Gmail 'Name <a@b.c>' header."""
    if not raw:
        return ""
    if "<" in raw and ">" in raw:
        return raw.split("<")[1].split(">")[0].strip()
    return raw.strip()


def _extract_name(raw: str) -> str:
    """Extract the display name from a Gmail 'Name <a@b.c>' header."""
    if not raw:
        return ""
    if "<" in raw and ">" in raw:
        return raw.split("<")[0].strip().strip('"').strip()
    return ""


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
    """Normalize a conversation message into clean plain chat text:
    strip HTML, decode entities, remove markdown emphasis/bullets and collapse whitespace."""
    if not text:
        return ""
    t = text
    t = re.split(r"(?i)<blockquote", t)[0]
    m = re.search(r"(?i)\bOn\b[^\n]*?\bwrote\s*:\s*(?:\n|$)?", t)
    if m is not None:
        t = t[: m.start()]
    t = re.sub(r"<br\s*/?>", "\n", t, flags=re.IGNORECASE)
    t = re.sub(r"</p\s*>", "\n", t, flags=re.IGNORECASE)
    t = re.sub(r"<[^>]+>", "", t)
    t = html_module.unescape(t)
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)
    t = re.sub(r"`(?!#)([^`]+?)`", r"\1", t)
    t = re.sub(r"(?m)^\s*#{1,6}\s*", "", t)
    t = re.sub(r"(?m)^\s*(?:[-*•]|\d+\.)\s+", "", t)
    return _collapse_ws(t)


def strip_email_quotes(body: str) -> str:
    """Reduce an inbound email to the customer's actual new message by removing
    quoted reply chains ('On ... wrote:', '-----Original Message-----', forwarded
    headers, '>' prefixed lines, HTML blockquotes and separators)."""
    if not body:
        return ""
    text = body
    # HTML blockquote = the quoted previous thread — cut everything from it on.
    text = re.split(r"(?i)<blockquote", text, maxsplit=1)[0]
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html_module.unescape(text)

    cut_patterns = [
        # Gmail-style "On Tue, Aug 11, 2026 at 9:08 PM Ai AceOne <a@b.c> wrote:"
        # (no leading-newline requirement: the quoted thread is often inline)
        re.compile(r"(?i)\bOn\b[^\n]*?\bwrote\s*:\s*(?:\n|$)?"),
        # Outlook "-----Original Message-----" / "-----Reply Message-----"
        re.compile(r"(?i)\n\s*[-_]{3,}\s*\n?\s*(Original Message|Reply Message)\s*[-_]{3,}"),
        # separator lines
        re.compile(r"\n\s*[-_]{4,}\s*\n"),
        # forwarded email headers
        re.compile(
            r"(?i)\n\s*(From|To|Sent|Cc|Bcc|Subject|Date|Reply-To|Return-Path|Message-ID|MIME-Version|Content-Type|Delivered-To):\s*\S"
        ),
        # quoted lines
        re.compile(r"\n\s*>"),
    ]
    for pat in cut_patterns:
        m = pat.search(text)
        if m is not None:
            text = text[: m.start()]
            break

    cleaned = _collapse_ws(text)
    return cleaned or body[:2000]


async def find_or_create_conversation(
    session: AsyncSession,
    workspace_id: str,
    email_account_id: str,
    customer_email: str,
    customer_name: str = "",
    subject: str = "",
    thread_id: Optional[str] = None,
    message_id: Optional[str] = None,
    ai_enabled: bool = True,
) -> EmailConversation:
    """Return the single stable conversation for (email_account, customer_email).

    One customer = ONE continuous conversation (WhatsApp-style). The provider
    thread id is mapped onto the conversation for correct reply threading."""
    customer_email = (customer_email or "").strip()
    if not customer_email:
        raise RuntimeError("No customer email to identify the conversation")

    result = await session.execute(
        select(EmailConversation)
        .where(
            EmailConversation.email_account_id == email_account_id,
            EmailConversation.customer_email.isnot(None),
            sa_func.lower(EmailConversation.customer_email) == customer_email.lower(),
        )
        .order_by(EmailConversation.created_at.asc())
    )
    existing = list(result.scalars().all())
    if existing:
        conv = existing[0]
        if thread_id and not conv.thread_id:
            conv.thread_id = thread_id
            conv.updated_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(conv)
        return conv

    conv_subject = (subject or "").strip()
    if conv_subject:
        conv_subject = (
            conv_subject
            if conv_subject.lower().startswith("re:")
            else f"Re: {conv_subject}"
        )
    else:
        conv_subject = f"Re: Conversation with {customer_name or customer_email}"

    conv = EmailConversation(
        workspace_id=workspace_id,
        email_account_id=email_account_id,
        lead_id=None,
        subject=conv_subject,
        status="active",
        ai_agent_active=ai_enabled,
        thread_id=thread_id or None,
        customer_email=customer_email,
        customer_name=customer_name or None,
        last_processed_message_id=message_id,
    )
    session.add(conv)
    await session.commit()
    await session.refresh(conv)
    return conv


async def start_conversation(
    session: AsyncSession,
    workspace_id: str,
    email_account_id: str,
    email_id: str,
    lead_name: str = "",
    lead_email: str = "",
    thread_id: str = "",
) -> EmailConversation:
    customer_email = lead_email or None
    customer_name = lead_name or None
    subject = ""
    body = ""

    # Server-side derivation: if the frontend couldn't resolve the customer
    # identity, fetch the email detail from the provider and pick the
    # counterparty (from for inbound, to for outbound/sent).
    account_result = await session.execute(
        select(EmailAccount).where(EmailAccount.id == email_account_id)
    )
    account = account_result.scalar_one_or_none()
    if account:
        try:
            from app.services import email_sync_service

            detail = await email_sync_service.get_email_detail(session, account, email_id)
            if detail:
                from_addr = _extract_email(detail.get("from", ""))
                to_addr = _extract_email(detail.get("to", ""))
                account_email = (account.email_address or "").lower()
                if from_addr and from_addr.lower() != account_email:
                    customer_email = customer_email or from_addr
                    customer_name = _extract_name(detail.get("from", "")) or customer_name
                elif to_addr:
                    customer_email = customer_email or to_addr
                    customer_name = _extract_name(detail.get("to", "")) or customer_name
                subject = detail.get("subject", "") or subject
                body = detail.get("body", "") or detail.get("snippet", "") or ""
        except Exception:
            pass

    if not customer_email:
        raise RuntimeError("No customer email identified for this message")

    conv = await find_or_create_conversation(
        session,
        workspace_id,
        email_account_id,
        customer_email,
        customer_name=customer_name or "",
        subject=subject,
        thread_id=thread_id or None,
        message_id=email_id,
        ai_enabled=True,
    )

    # Append the customer's inbound message to the conversation (dedup by
    # provider message id so re-starts never duplicate it).
    already = await session.execute(
        select(EmailConversationMessage).where(
            EmailConversationMessage.conversation_id == conv.id,
            EmailConversationMessage.provider_message_id == email_id,
        )
    )
    if already.scalar_one_or_none() is None:
        session.add(
            EmailConversationMessage(
                conversation_id=conv.id,
                sender_type="customer",
                direction="inbound",
                content=strip_email_quotes(body) or f"({subject or 'Email'})",
                is_approved=True,
                sent_at=datetime.now(timezone.utc),
                provider_message_id=email_id,
            )
        )
        conv.last_processed_message_id = email_id
        conv.updated_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(conv)

    if not conv.ai_agent_active or conv.status != "active":
        conv.ai_agent_active = True
        conv.status = "active"
        conv.updated_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(conv)

    return conv


async def send_conversation_message(
    session: AsyncSession,
    conversation_id: str,
    message: str,
    sender_type: str = "user",
) -> EmailConversationMessage:
    msg = EmailConversationMessage(
        conversation_id=conversation_id,
        sender_type=sender_type,
        content=message,
    )
    session.add(msg)
    await session.commit()
    await session.refresh(msg)
    return msg


async def send_reply_email(
    session: AsyncSession,
    conversation_id: str,
    message: str,
) -> dict:
    """Manually reply to the customer: send a real email + log it as a user/ai message."""
    from app.db.models.email_account import EmailAccount
    from app.services import email_sync_service

    result = await session.execute(
        select(EmailConversation).where(EmailConversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise RuntimeError("Conversation not found")

    account_result = await session.execute(
        select(EmailAccount).where(EmailAccount.id == conv.email_account_id)
    )
    account = account_result.scalar_one_or_none()
    if not account:
        raise RuntimeError("Email account not found")

    customer_email = conv.customer_email
    if not customer_email and conv.last_processed_message_id:
        try:
            detail = await email_sync_service.get_email_detail(
                session, account, conv.last_processed_message_id
            )
            if detail:
                from_addr = _extract_email(detail.get("from", ""))
                to_addr = _extract_email(detail.get("to", ""))
                account_email = (account.email_address or "").lower()
                if from_addr and from_addr.lower() != account_email:
                    customer_email = from_addr
                elif to_addr:
                    customer_email = to_addr
                if customer_email:
                    conv.customer_email = customer_email
                    await session.commit()
        except Exception:
            customer_email = None

    if not customer_email:
        raise RuntimeError("No customer email on this conversation")

    subject = f"Re: {conv.subject}" if not conv.subject.startswith("Re:") else conv.subject

    send_result = await email_sync_service.send_email_from_account(
        session, account, customer_email, subject, message, conv.thread_id
    )
    outbound_id = None
    if send_result:
        outbound_id = (
            send_result.get("id")
            or send_result.get("messageId")
            or send_result.get("email_message_id")
        )

    msg = EmailConversationMessage(
        conversation_id=conversation_id,
        sender_type="user",
        direction="outbound",
        content=message,
        is_approved=True,
        sent_at=datetime.now(timezone.utc),
        provider_message_id=outbound_id,
    )
    session.add(msg)
    await session.commit()
    await session.refresh(msg)
    return {"status": "sent", "message": msg.content}


async def stop_conversation(
    session: AsyncSession, conversation_id: str
) -> bool:
    result = await session.execute(
        select(EmailConversation).where(EmailConversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
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
    result = await session.execute(
        select(EmailConversation).where(EmailConversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        return False
    conv.ai_agent_active = True
    conv.status = "active"
    conv.updated_at = datetime.now(timezone.utc)
    await session.commit()
    return True


async def book_meeting(
    session: AsyncSession,
    workspace_id: str,
    conversation_id: Optional[str],
    lead_name: str,
    lead_email: str,
    lead_company: str,
    meeting_datetime: str,
) -> dict:
    from app.db.models.email_account import EmailConversation, EmailConversationMessage
    from app.db.models.lead import Lead
    from app.db.models.crm import CrmEntry
    import sqlalchemy as sa

    # Upsert the lead (find by email lower-case) and promote it to Hot.
    lead_result = await session.execute(
        select(Lead).where(
            sa.and_(
                Lead.workspace_id == workspace_id,
                sa.func.lower(Lead.email) == sa.func.lower(lead_email),
            )
        )
    )
    lead = lead_result.scalar_one_or_none()

    if lead is None:
        lead = Lead(
            workspace_id=workspace_id,
            name=lead_name or lead_email or "Unknown lead",
            email=lead_email or None,
            company=lead_company or None,
            source="email_agent",
            status="Hot",
        )
        session.add(lead)
        await session.flush()
    else:
        lead.status = "Hot"
        lead.updated_at = datetime.now(timezone.utc)
        if lead_company and not lead.company:
            lead.company = lead_company

    # Add to CRM box if not already there (dedupe by workspace + lead).
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

    conversation = None
    if conversation_id:
        conv_res = await session.execute(
            select(EmailConversation).where(EmailConversation.id == conversation_id)
        )
        conversation = conv_res.scalar_one_or_none()

    booking_ref = f"BKG-{uuid.uuid4().hex[:8].upper()}"

    if conversation:
        msg = EmailConversationMessage(
            conversation_id=conversation.id,
            sender_type="system",
            content=f"Meeting booked! Reference: {booking_ref}. Date: {meeting_datetime}. Lead: {lead_name}.",
        )
        session.add(msg)

    await session.commit()

    return {
        "booking_ref": booking_ref,
        "lead_name": lead_name,
        "lead_email": lead_email,
        "lead_company": lead_company,
        "meeting_datetime": meeting_datetime,
        "lead_id": lead.id,
    }


async def export_booked_leads_csv(
    session: AsyncSession, workspace_id: str
) -> str:
    from app.db.models.email_account import EmailConversationMessage
    import io
    import csv

    result = await session.execute(
        sa.text("""
            SELECT m.content, m.created_at
            FROM email_conversation_messages m
            JOIN email_conversations c ON m.conversation_id = c.id
            WHERE c.workspace_id = :ws AND m.sender_type = 'system'
              AND m.content LIKE 'Meeting booked!%'
            ORDER BY m.created_at DESC
        """),
        {"ws": workspace_id}
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Booking Ref", "Lead Name", "Lead Email", "Company", "Meeting Date", "Created At"])

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
            parts.get("Email", ""),
            parts.get("Company", ""),
            parts.get("Date", ""),
            created_at.strftime("%Y-%m-%d %H:%M:%S") if created_at else "",
        ])

    return output.getvalue()


async def get_active_conversations(
    session: AsyncSession, workspace_id: str, account_id: str
) -> list[EmailConversation]:
    """All conversations for an account (active or paused) so the UI can keep
    one stable conversation per customer even after the receptionist is stopped."""
    result = await session.execute(
        select(EmailConversation).where(
            EmailConversation.workspace_id == workspace_id,
            EmailConversation.email_account_id == account_id,
        ).order_by(EmailConversation.updated_at.desc())
    )
    return list(result.scalars().all())


async def list_conversation_previews(
    session: AsyncSession, account_id: str, page: int = 1, page_size: int = 10
) -> tuple[list[dict], int, bool]:
    """WhatsApp-style Inbox preview: ONE row per customer (conversation),
    showing only the latest normalized actual message + timestamp, ordered
    by the latest message's real timestamp (not creation/thread time)."""
    from sqlalchemy import func as sa_func

    conv_result = await session.execute(
        select(EmailConversation).where(
            EmailConversation.email_account_id == account_id
        ).order_by(EmailConversation.updated_at.desc())
    )
    all_convs = list(conv_result.scalars().all())
    total = len(all_convs)

    booked_ids = set(
        (await session.execute(
            select(EmailConversationMessage.conversation_id)
            .where(
                EmailConversationMessage.sender_type == "system",
                EmailConversationMessage.content.like("Meeting booked!%"),
            )
        )).scalars().all()
    )

    start = (page - 1) * page_size
    page_convs = all_convs[start:start + page_size]

    items: list[dict] = []
    for conv in page_convs:
        msg_result = await session.execute(
            select(EmailConversationMessage)
            .where(EmailConversationMessage.conversation_id == conv.id)
            .order_by(sa_func.coalesce(EmailConversationMessage.sent_at, EmailConversationMessage.created_at))
        )
        msgs = list(msg_result.scalars().all())
        last = msgs[-1] if msgs else None
        items.append({
            "id": conv.id,
            "customer_name": conv.customer_name or conv.customer_email,
            "customer_email": conv.customer_email,
            "last_message": clean_message_content(last.content) if last else "",
            "last_message_sender_type": last.sender_type if last else "",
            "last_message_at": (last.sent_at or last.created_at) if last else conv.updated_at,
            "ai_agent_active": conv.ai_agent_active,
            "status": conv.status,
            "is_booked": conv.id in booked_ids,
        })

    return items, total, (start + page_size) < total
