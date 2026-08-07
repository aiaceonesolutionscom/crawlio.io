import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.email_account import EmailAccount, EmailDraft
from app.db.models.email import EmailMessage
from app.services.email_account_service import check_daily_quota, increment_sent_count
from app.services.email_service import send_email as brevo_send_email


async def create_draft(
    session: AsyncSession,
    workspace_id: str,
    email_account_id: str,
    subject: str,
    body: str,
    kind: str = "composed",
    recipient_emails: Optional[list[str]] = None,
    lead_id: Optional[str] = None,
    ai_prompt: Optional[str] = None,
    conversation_id: Optional[str] = None,
) -> EmailDraft:
    draft = EmailDraft(
        workspace_id=workspace_id,
        email_account_id=email_account_id,
        lead_id=lead_id,
        subject=subject,
        body=body,
        kind=kind,
        status="draft",
        recipient_emails=json.dumps(recipient_emails) if recipient_emails else None,
        ai_prompt=ai_prompt,
        conversation_id=conversation_id,
    )
    session.add(draft)
    await session.commit()
    await session.refresh(draft)
    return draft


async def update_draft(
    session: AsyncSession,
    draft_id: str,
    subject: Optional[str] = None,
    body: Optional[str] = None,
    recipient_emails: Optional[list[str]] = None,
) -> Optional[EmailDraft]:
    result = await session.execute(select(EmailDraft).where(EmailDraft.id == draft_id))
    draft = result.scalar_one_or_none()
    if not draft:
        return None

    if subject is not None:
        draft.subject = subject
    if body is not None:
        draft.body = body
    if recipient_emails is not None:
        draft.recipient_emails = json.dumps(recipient_emails)

    draft.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(draft)
    return draft


async def send_draft(session: AsyncSession, draft_id: str) -> Optional[EmailMessage]:
    result = await session.execute(select(EmailDraft).where(EmailDraft.id == draft_id))
    draft = result.scalar_one_or_none()
    if not draft or draft.status == "sent":
        return None

    quota = await check_daily_quota(session, draft.workspace_id, draft.email_account_id)
    if quota["remaining"] <= 0:
        raise RuntimeError("Daily email limit reached")

    account_result = await session.execute(
        select(EmailAccount).where(EmailAccount.id == draft.email_account_id)
    )
    account = account_result.scalar_one_or_none()
    if not account:
        raise RuntimeError("Email account not found")

    recipients = json.loads(draft.recipient_emails) if draft.recipient_emails else []

    email_message = EmailMessage(
        workspace_id=draft.workspace_id,
        lead_id=draft.lead_id,
        to_email=", ".join(recipients),
        subject=draft.subject,
        kind=draft.kind,
        status="queued",
    )
    session.add(email_message)
    await session.commit()
    await session.refresh(email_message)

    try:
        for recipient in recipients:
            await brevo_send_email(recipient, draft.subject, draft.body)

        email_message.status = "sent"
        email_message.sent_at = datetime.now(timezone.utc)
        draft.status = "sent"
        draft.updated_at = datetime.now(timezone.utc)

        await increment_sent_count(
            session, draft.workspace_id, draft.email_account_id, draft.kind
        )
    except Exception as exc:
        email_message.status = "failed"
        email_message.error = str(exc)[:500]
        draft.status = "draft"
        draft.updated_at = datetime.now(timezone.utc)

    await session.commit()
    await session.refresh(email_message)
    return email_message


async def list_drafts(
    session: AsyncSession, workspace_id: str, status: Optional[str] = None
) -> list[EmailDraft]:
    query = select(EmailDraft).where(EmailDraft.workspace_id == workspace_id)
    if status:
        query = query.where(EmailDraft.status == status)
    query = query.order_by(EmailDraft.created_at.desc())
    result = await session.execute(query)
    return list(result.scalars().all())


async def archive_draft(session: AsyncSession, draft_id: str) -> bool:
    result = await session.execute(select(EmailDraft).where(EmailDraft.id == draft_id))
    draft = result.scalar_one_or_none()
    if not draft:
        return False

    draft.status = "archived"
    draft.updated_at = datetime.now(timezone.utc)
    await session.commit()
    return True
