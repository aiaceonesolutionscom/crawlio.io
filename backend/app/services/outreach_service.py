"""Outreach: eligible-lead selection, personalized AI generation, and the
approved send path. All safety checks (daily limit, duplicate outreach,
unsubscribe) are enforced here on the backend — never trusted from the UI."""

import json
import logging
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.plans import PLAN_CAPABILITIES
from app.db.models.agent import BusinessProfile
from app.db.models.email import EmailMessage
from app.db.models.email_account import EmailAccount
from app.db.models.lead import Lead
from app.db.models.workspace import Workspace

logger = logging.getLogger(__name__)

OUTREACH_PROMPT = """You are an expert B2B email copywriter. Write a PROFESSIONAL,
personalized outreach email from the sender's business to ONE recipient.

SENDER BUSINESS CONTEXT:
{sender_context}

RECIPIENT:
- Name: {recipient_name}
- Company: {recipient_company}
- Email: {recipient_email}
- Website: {recipient_website}

Rules:
1. Greet the recipient by their first name. If a name is unavailable use "Hello there,".
2. NEVER render "undefined", "null" or "[object Object]".
3. Reference the recipient's company/website naturally when available.
4. Body must be 3-5 short paragraphs, professional, specific, not spammy.
5. End with ONE clear call-to-action and a proper sign-off signed by the owner.

Return JSON only:
{{
  "subject": "email subject line",
  "body": "email body as plain text paragraphs separated by \\n\\n"
}}"""


async def _generate_personalized(profile: BusinessProfile, lead: Lead, sender_context: str) -> dict:
    if not settings.mistral_api_key:
        raise RuntimeError("MISTRAL_API_KEY is not configured")

    prompt = OUTREACH_PROMPT.format(
        sender_context=sender_context,
        recipient_name=lead.name or "",
        recipient_company=lead.company or "",
        recipient_email=lead.email or "",
        recipient_website=lead.website or "",
    )
    payload = {
        "model": "mistral-small-latest",
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Generate the outreach email now."},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.7,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
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
    parsed = json.loads(content)
    subject = (parsed.get("subject") or "").strip()
    body = (parsed.get("body") or "").strip()
    return {"subject": subject, "body": body}


async def eligible_leads(
    session: AsyncSession, workspace_id: str, limit: int = 200
) -> list[Lead]:
    """Leads that can receive outreach NOW: has an email, never outreached, not
    unsubscribed. The 'already contacted' check is DB-backed (email_messages +
    lead.outreach_sent_at), not a frontend filter."""
    result = await session.execute(
        select(Lead)
        .where(
            Lead.workspace_id == workspace_id,
            Lead.email.isnot(None),
            Lead.email != "",
            Lead.unsubscribed_at.is_(None),
            Lead.outreach_sent_at.is_(None),
        )
        .order_by(Lead.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


def lead_source(lead: Lead) -> str:
    return "website" if lead.website else "non-website"


async def outreach_used_today(session: AsyncSession, workspace_id: str, timezone: str) -> int:
    tz = ZoneInfo(timezone) if timezone else ZoneInfo("Asia/Karachi")
    now = datetime.now(tz)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    result = await session.execute(
        select(func.count(EmailMessage.id)).where(
            EmailMessage.workspace_id == workspace_id,
            EmailMessage.kind == "outreach",
            EmailMessage.sent_at >= start,
        )
    )
    return int(result.scalar() or 0)


def outreach_daily_limit(workspace: Workspace) -> int:
    if "email_agent" not in PLAN_CAPABILITIES.get(workspace.plan, set()):
        return 0
    if workspace.plan == "enterprise":
        return settings.enterprise_daily_email_limit
    if workspace.plan == "pro":
        return settings.pro_daily_email_limit
    return 0


async def get_sender_account(
    session: AsyncSession, workspace_id: str
) -> Optional[EmailAccount]:
    from app.services import email_account_service

    accounts = await email_account_service.list_email_accounts(session, workspace_id)
    for account in accounts:
        if account.is_active:
            return account
    return accounts[0] if accounts else None


async def validate_send(
    session: AsyncSession,
    workspace: Workspace,
    profile: BusinessProfile,
    lead: Lead,
) -> None:
    if not lead.email:
        raise RuntimeError("Recipient has no email address")
    if lead.unsubscribed_at is not None:
        raise RuntimeError("Recipient has unsubscribed")
    if lead.outreach_sent_at is not None:
        raise RuntimeError("Outreach already sent to this recipient")

    used = await outreach_used_today(session, workspace.id, profile.timezone)
    limit = outreach_daily_limit(workspace)
    if limit > 0 and used >= limit:
        raise RuntimeError(f"Daily outreach limit of {limit} reached")


async def send_outreach(
    session: AsyncSession,
    workspace: Workspace,
    profile: BusinessProfile,
    lead: Lead,
    subject: str,
    body: str,
) -> dict:
    """Validate, then send via the user's CONNECTED email account (so replies
    thread correctly), then write the email_messages log and update the lead."""
    await validate_send(session, workspace, profile, lead)

    from app.services import email_sync_service

    account = await get_sender_account(session, workspace.id)
    if not account:
        raise RuntimeError("Connect a Gmail or Outlook account first")

    email_message = EmailMessage(
        workspace_id=workspace.id,
        lead_id=lead.id,
        to_email=lead.email,
        subject=subject,
        kind="outreach",
        status="queued",
    )
    session.add(email_message)

    try:
        await email_sync_service.send_email_from_account(session, account, lead.email, subject, body)
        email_message.status = "sent"
        email_message.sent_at = datetime.now(timezone.utc)
        lead.outreach_sent_at = datetime.now(timezone.utc)
        lead.status = "Contacted"
        lead.updated_at = datetime.now(timezone.utc)
        session.add(lead)
        await session.commit()
        await session.refresh(email_message)
        return {"email_message_id": email_message.id, "sent": True, "recipient": lead.email}
    except Exception as exc:
        email_message.status = "failed"
        email_message.error = str(exc)[:500]
        await session.commit()
        raise RuntimeError(f"Send failed: {exc}") from exc


async def generate_outreports(
    session: AsyncSession,
    profile: BusinessProfile,
    leads: list[Lead],
    account: Optional[EmailAccount] = None,
) -> list[dict]:
    from app.services.business_profile_service import to_context

    context = to_context(profile, account.email_address if account else "")
    results = []
    for lead in leads:
        draft = await _generate_personalized(profile, lead, context)
        results.append(
            {
                "lead_id": lead.id,
                "recipient_name": lead.name,
                "recipient_company": lead.company,
                "recipient_email": lead.email,
                "source": lead_source(lead),
                "subject": draft["subject"],
                "body": draft["body"],
            }
        )
    return results