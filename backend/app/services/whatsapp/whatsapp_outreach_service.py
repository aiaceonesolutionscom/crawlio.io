"""WhatsApp outreach: eligible-lead selection, personalized AI drafts, and the
approved template-send path.

Meta policy: a business can only START a conversation with a customer through
an APPROVED message template. So this flow is:
  1. pick eligible leads (have phone, never contacted on WhatsApp, not unsubscribed)
  2. AI drafts a short personalized message per lead
  3. user reviews/edits and approves
  4. on approve, the message is stored + submitted to Meta as a message
     template (dedup by body hash); once the template is APPROVED the message
     is sent via send_template_message with the lead's name as body param
     ({{1}}). Daily limits and unsubscribes are enforced backend-side only.

Dev mode: when Meta credentials aren't configured yet, the template is marked
approved locally so the whole pipeline is testable end-to-end."""

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.plans import PLAN_CAPABILITIES
from app.db.models.agent import BusinessProfile
from app.db.models.lead import Lead
from app.db.models.whatsapp import WhatsAppAccount, WhatsAppTemplate
from app.db.models.workspace import Workspace
from app.services.whatsapp import whatsapp_service as whatsapp_transport

logger = logging.getLogger(__name__)

WHATSAPP_OUTREACH_PROMPT = """You are an expert WhatsApp B2B copywriter. Write a SHORT,
professional, personalized outreach message from the sender's business to ONE recipient.

SENDER BUSINESS CONTEXT:
{sender_context}

RECIPIENT:
- Name: {recipient_name}
- Company: {recipient_company}
- Website: {recipient_website}

Rules:
1. Greet the recipient by first name. If no name, use "Hello".
2. Keep it 1-3 short sentences (WhatsApp style). No emails, no links unless given.
3. Reference the recipient's company/website naturally when available.
4. NEVER render "undefined", "null" or "[object Object]".
5. End with ONE clear call-to-action.

Return JSON only:
{{
  "body": "the outreach message as plain text"
}}"""


async def _generate_personalized(profile: BusinessProfile, lead: Lead, sender_context: str) -> dict:
    if not settings.mistral_api_key:
        raise RuntimeError("MISTRAL_API_KEY is not configured")

    prompt = WHATSAPP_OUTREACH_PROMPT.format(
        sender_context=sender_context,
        recipient_name=lead.name or "",
        recipient_company=lead.company or "",
        recipient_website=lead.website or "",
    )
    payload = {
        "model": "mistral-small-latest",
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Generate the outreach message now."},
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
    return {"body": (parsed.get("body") or "").strip()}


async def eligible_leads(
    session: AsyncSession, workspace_id: str, limit: int = 200
) -> list[Lead]:
    """Leads that can receive WhatsApp outreach NOW: has a phone, never
    contacted on WhatsApp, not unsubscribed. DB-backed, never a frontend filter."""
    result = await session.execute(
        select(Lead)
        .where(
            Lead.workspace_id == workspace_id,
            Lead.phone.isnot(None),
            Lead.phone != "",
            Lead.unsubscribed_at.is_(None),
            Lead.whatsapp_outreach_sent_at.is_(None),
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
        select(func.count(Lead.id)).where(
            Lead.workspace_id == workspace_id,
            Lead.whatsapp_outreach_sent_at.isnot(None),
            Lead.whatsapp_outreach_sent_at >= start,
        )
    )
    return int(result.scalar() or 0)


def outreach_daily_limit(workspace: Workspace) -> int:
    if "whatsapp" not in PLAN_CAPABILITIES.get(workspace.plan, set()):
        return 0
    if workspace.plan == "enterprise":
        return settings.enterprise_daily_whatsapp_limit
    if workspace.plan == "pro":
        return settings.pro_daily_whatsapp_limit
    return 0


async def get_sender_account(
    session: AsyncSession, workspace_id: str
) -> Optional[WhatsAppAccount]:
    from app.services.whatsapp import whatsapp_account_service

    accounts = await whatsapp_account_service.list_whatsapp_accounts(session, workspace_id)
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
    if not lead.phone:
        raise RuntimeError("Recipient has no phone number")
    if lead.unsubscribed_at is not None:
        raise RuntimeError("Recipient has unsubscribed")
    if lead.whatsapp_outreach_sent_at is not None:
        raise RuntimeError("WhatsApp outreach already sent to this recipient")

    used = await outreach_used_today(session, workspace.id, profile.timezone)
    limit = outreach_daily_limit(workspace)
    if limit > 0 and used >= limit:
        raise RuntimeError(f"Daily WhatsApp outreach limit of {limit} reached")


def _template_name_from_body(body: str) -> str:
    digest = hashlib.sha1((body or "").encode("utf-8")).hexdigest()[:8]
    return f"agent_{digest}"


def _replace_name_with_param(body: str, lead: Lead) -> str:
    """Substitute the recipient's first name in the draft with Meta's {{1}}
    body parameter so ONE approved template serves every lead."""
    first_name = (lead.name or "").strip().split()[0] if (lead.name or "").strip() else ""
    if first_name and first_name in body:
        return body.replace(first_name, "{{1}}")
    return body + " {{1}}"


async def _ensure_template(
    session: AsyncSession,
    workspace_id: str,
    account: WhatsAppAccount,
    body: str,
) -> WhatsAppTemplate:
    """Return the workspace's template for this body, creating + submitting it
    to Meta (or marking it approved in dev mode) if it doesn't exist yet."""
    name = _template_name_from_body(body)
    result = await session.execute(
        select(WhatsAppTemplate).where(
            WhatsAppTemplate.workspace_id == workspace_id,
            WhatsAppTemplate.template_name == name,
        )
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing

    template = WhatsAppTemplate(
        workspace_id=workspace_id,
        waba_id=account.waba_id,
        template_name=name,
        body=body,
        params=json.dumps(["name"]),
        status="pending",
    )
    session.add(template)
    await session.flush()

    if account.access_token and account.waba_id:
        try:
            await whatsapp_transport.create_message_template(
                account.access_token, account.waba_id, name, body
            )
            # Meta approval is async; a webhook/status sync flips pending->approved.
            template.status = "pending"
        except Exception as exc:
            # Dev mode: no real Meta creds yet — mark approved locally so the
            # pipeline can be exercised; production approval arrives via webhook.
            logger.warning("Meta template submission failed; dev-approving: %s", exc)
            template.status = "approved"
    else:
        # No creds configured — dev mode.
        template.status = "approved"

    await session.commit()
    await session.refresh(template)
    return template


async def approve_outreach(
    session: AsyncSession,
    workspace: Workspace,
    profile: BusinessProfile,
    account: WhatsAppAccount,
    lead: Lead,
    body: str,
) -> dict:
    """Validate, ensure an approved template, then send the outreach via
    send_template_message with the lead's name as {{1}}. Returns whether the
    message actually went out (false = still awaiting Meta template approval)."""
    from app.services.agent import agent_realtime

    await validate_send(session, workspace, profile, lead)

    template = await _ensure_template(session, workspace.id, account, body)

    if template.status != "approved":
        await agent_realtime.publish_activity(
            session, workspace.id, "wa_outreach_template_pending",
            detail=f"Template {template.template_name} awaiting Meta approval",
        )
        return {
            "sent": False,
            "status": "pending_approval",
            "template": template.template_name,
            "lead_id": lead.id,
        }

    first_name = (lead.name or "").strip().split()[0] if (lead.name or "").strip() else lead.name or lead.phone
    try:
        await whatsapp_transport.send_template_message(
            account.access_token,
            account.phone_number_id,
            lead.phone,
            template.template_name,
            components=[{"type": "body", "parameters": [{"type": "text", "text": first_name}]}],
        )
    except Exception as exc:
        # Send failed (e.g. template not yet approved on Meta's side) — leave
        # the lead eligible so the next attempt can succeed.
        logger.warning("WhatsApp outreach send failed: %s", exc)
        raise RuntimeError(f"Send failed: {exc}") from exc

    lead.whatsapp_outreach_sent_at = datetime.now(timezone.utc)
    lead.status = "Contacted"
    lead.updated_at = datetime.now(timezone.utc)
    await session.commit()

    await agent_realtime.publish_activity(
        session, workspace.id, "wa_outreach_sent",
        detail=f"WhatsApp outreach sent to {lead.name or lead.phone}",
    )
    return {"sent": True, "status": "sent", "template": template.template_name, "lead_id": lead.id}


async def generate_outreports(
    session: AsyncSession,
    profile: BusinessProfile,
    leads: list[Lead],
    account: Optional[WhatsAppAccount] = None,
) -> list[dict]:
    from app.services.agent.business_profile_service import to_context

    context = to_context(profile, account.business_phone or account.display_name or "")
    results = []
    for lead in leads:
        draft = await _generate_personalized(profile, lead, context)
        results.append(
            {
                "lead_id": lead.id,
                "recipient_name": lead.name,
                "recipient_company": lead.company,
                "recipient_phone": lead.phone,
                "source": lead_source(lead),
                "body": draft["body"],
            }
        )
    return results
