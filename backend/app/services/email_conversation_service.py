import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.email_account import EmailAccount, EmailConversation, EmailConversationMessage, EmailDraft, DailyEmailQuota
from app.services import email_account_service


async def start_conversation(
    session: AsyncSession,
    workspace_id: str,
    email_account_id: str,
    email_id: str,
    lead_name: str = "",
    lead_email: str = "",
) -> EmailConversation:
    conv = EmailConversation(
        workspace_id=workspace_id,
        email_account_id=email_account_id,
        lead_id=None,
        subject=f"Re: Conversation with {lead_name or lead_email}",
        status="active",
        ai_agent_active=True,
        customer_email=lead_email or None,
        customer_name=lead_name or None,
    )
    session.add(conv)
    await session.commit()
    await session.refresh(conv)

    initial_msg = EmailConversationMessage(
        conversation_id=conv.id,
        sender_type="ai",
        content=f"Hello! I'm your AI receptionist from Crawlio. How can I help you today?",
    )
    session.add(initial_msg)
    await session.commit()

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
    if not conv.customer_email:
        raise RuntimeError("No customer email on this conversation")

    account_result = await session.execute(
        select(EmailAccount).where(EmailAccount.id == conv.email_account_id)
    )
    account = account_result.scalar_one_or_none()
    if not account:
        raise RuntimeError("Email account not found")

    subject = f"Re: {conv.subject}" if not conv.subject.startswith("Re:") else conv.subject

    await email_sync_service.send_email_from_account(
        session, account, conv.customer_email, subject, message
    )

    msg = EmailConversationMessage(
        conversation_id=conversation_id,
        sender_type="user",
        content=message,
        is_approved=True,
        sent_at=datetime.now(timezone.utc),
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
    result = await session.execute(
        select(EmailConversation).where(
            EmailConversation.workspace_id == workspace_id,
            EmailConversation.email_account_id == account_id,
            EmailConversation.status == "active"
        ).order_by(EmailConversation.created_at.desc())
    )
    return list(result.scalars().all())
