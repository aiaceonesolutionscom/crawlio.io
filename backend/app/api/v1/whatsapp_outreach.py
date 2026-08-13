"""WhatsApp outreach API: eligible-lead selector, AI draft generation + approve,
template status, usage. Mirrors the email outreach flow in agent.py."""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_workspace, require_plan
from app.db.models.agent import BusinessProfile
from app.db.models.lead import Lead
from app.db.models.workspace import Workspace
from app.db.session import get_session
from app.services import (
    business_profile_service,
    whatsapp_outreach_service,
)

router = APIRouter(prefix="/whatsapp-outreach", tags=["whatsapp-outreach"])


class EligibleLeadRead(BaseModel):
    lead_id: str
    name: str
    company: Optional[str] = None
    phone: str
    website: Optional[str] = None
    source: str


class OutreachUsage(BaseModel):
    used: int
    limit: int
    remaining: int


class OutreachGenerateRequest(BaseModel):
    lead_ids: list[str] = Field(default_factory=list)


class OutreachRegenerateRequest(BaseModel):
    lead_id: str
    instruction: str = ""
    current_body: str = ""


class OutreachDraftRead(BaseModel):
    lead_id: str
    recipient_name: str = ""
    recipient_company: Optional[str] = None
    recipient_phone: str = ""
    source: str
    body: str


class OutreachApproveItem(BaseModel):
    lead_id: str
    body: str


class OutreachApproveRequest(BaseModel):
    items: list[OutreachApproveItem]


class OutreachApproveResult(BaseModel):
    lead_id: str
    sent: bool
    status: str
    template: Optional[str] = None
    error: Optional[str] = None


class OutreachApproveResponse(BaseModel):
    sent: int
    pending: int
    rejected: int
    results: list[OutreachApproveResult]


class TemplateRead(BaseModel):
    id: str
    template_name: str
    body: str
    status: str
    params: str


async def _find_lead(session: AsyncSession, workspace_id: str, lead_id: str) -> Lead:
    result = await session.execute(
        select(Lead).where(Lead.id == lead_id, Lead.workspace_id == workspace_id)
    )
    lead = result.scalar_one_or_none()
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return lead


async def _require_account(session: AsyncSession, workspace_id: str):
    account = await whatsapp_outreach_service.get_sender_account(session, workspace_id)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Connect a WhatsApp Business number first",
        )
    return account


@router.get("/usage", response_model=OutreachUsage)
async def get_outreach_usage(
    workspace: Annotated[Workspace, Depends(require_plan("whatsapp"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    profile = await business_profile_service.get_profile(session, workspace.id)
    tz = profile.timezone if profile else "Asia/Karachi"
    used = await whatsapp_outreach_service.outreach_used_today(session, workspace.id, tz)
    limit = whatsapp_outreach_service.outreach_daily_limit(workspace)
    return OutreachUsage(used=used, limit=limit, remaining=max(0, limit - used))


@router.get("/eligible-leads", response_model=list[EligibleLeadRead])
async def get_eligible_leads(
    workspace: Annotated[Workspace, Depends(require_plan("whatsapp"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    leads = await whatsapp_outreach_service.eligible_leads(session, workspace.id)
    return [
        EligibleLeadRead(
            lead_id=lead.id,
            name=lead.name,
            company=lead.company,
            phone=lead.phone or "",
            website=lead.website,
            source=whatsapp_outreach_service.lead_source(lead),
        )
        for lead in leads
    ]


@router.post("/generate", response_model=list[OutreachDraftRead])
async def generate_outreach(
    payload: OutreachGenerateRequest,
    workspace: Annotated[Workspace, Depends(require_plan("whatsapp"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    profile = await business_profile_service.get_profile(session, workspace.id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Set up your business profile first")
    if not payload.lead_ids:
        return []

    result = await session.execute(
        select(Lead).where(
            Lead.id.in_(payload.lead_ids),
            Lead.workspace_id == workspace.id,
        )
    )
    leads = list(result.scalars().all())
    ordered = [l for l in leads if l.id in payload.lead_ids]
    account = await whatsapp_outreach_service.get_sender_account(session, workspace.id)
    drafts = await whatsapp_outreach_service.generate_outreports(session, profile, ordered, account)
    return [OutreachDraftRead(**d) for d in drafts]


@router.post("/regenerate", response_model=OutreachDraftRead)
async def regenerate_outreach(
    payload: OutreachRegenerateRequest,
    workspace: Annotated[Workspace, Depends(require_plan("whatsapp"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    lead = await _find_lead(session, workspace.id, payload.lead_id)
    profile = await business_profile_service.get_profile(session, workspace.id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Set up your business profile first")

    account = await whatsapp_outreach_service.get_sender_account(session, workspace.id)
    drafts = await whatsapp_outreach_service.generate_outreports(session, profile, [lead], account)
    if not drafts:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Generation failed")
    return OutreachDraftRead(**drafts[0])


@router.post("/approve", response_model=OutreachApproveResponse)
async def approve_outreach(
    payload: OutreachApproveRequest,
    workspace: Annotated[Workspace, Depends(require_plan("whatsapp"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    if not payload.items:
        return OutreachApproveResponse(sent=0, pending=0, rejected=0, results=[])

    profile = await business_profile_service.get_profile(session, workspace.id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Set up your business profile first")
    account = await _require_account(session, workspace.id)

    results = []
    sent = 0
    pending = 0
    rejected = 0
    for item in payload.items:
        lead = await _find_lead(session, workspace.id, item.lead_id)
        try:
            outcome = await whatsapp_outreach_service.approve_outreach(
                session, workspace, profile, account, lead, item.body
            )
            if outcome.get("sent"):
                sent += 1
            else:
                pending += 1
            results.append(
                OutreachApproveResult(
                    lead_id=item.lead_id,
                    sent=bool(outcome.get("sent")),
                    status=outcome.get("status", ""),
                    template=outcome.get("template"),
                )
            )
        except Exception as exc:
            rejected += 1
            results.append(
                OutreachApproveResult(
                    lead_id=item.lead_id,
                    sent=False,
                    status="rejected",
                    error=str(exc),
                )
            )

    return OutreachApproveResponse(sent=sent, pending=pending, rejected=rejected, results=results)


@router.get("/templates", response_model=list[TemplateRead])
async def list_templates(
    workspace: Annotated[Workspace, Depends(require_plan("whatsapp"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    from app.db.models.whatsapp import WhatsAppTemplate

    result = await session.execute(
        select(WhatsAppTemplate)
        .where(WhatsAppTemplate.workspace_id == workspace.id)
        .order_by(WhatsAppTemplate.created_at.desc())
        .limit(100)
    )
    return [
        TemplateRead(
            id=t.id,
            template_name=t.template_name,
            body=t.body,
            status=t.status,
            params=t.params,
        )
        for t in result.scalars().all()
    ]


@router.post("/templates/sync", response_model=list[TemplateRead])
async def sync_templates(
    workspace: Annotated[Workspace, Depends(require_plan("whatsapp"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    """Pull message-template statuses from Meta and sync them into the local
    whatsapp_templates rows. pending -> approved/rejected as Meta finishes
    reviewing, so previously-queued outreach can then be sent."""
    from app.db.models.whatsapp import WhatsAppTemplate
    from app.services import whatsapp_service

    account = await _require_account(session, workspace.id)
    if not (account.access_token and account.waba_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="WhatsApp account is not fully connected (missing token/WABA)",
        )

    remote = await whatsapp_service.list_message_templates(account.access_token, account.waba_id)
    status_map = {t.get("name"): (t.get("status") or "").lower() for t in remote}

    result = await session.execute(
        select(WhatsAppTemplate).where(WhatsAppTemplate.workspace_id == workspace.id)
    )
    templates = list(result.scalars().all())
    for t in templates:
        remote_status = status_map.get(t.template_name)
        if remote_status == "approved":
            t.status = "approved"
        elif remote_status == "rejected":
            t.status = "rejected"
    await session.commit()

    return [
        TemplateRead(
            id=t.id,
            template_name=t.template_name,
            body=t.body,
            status=t.status,
            params=t.params,
        )
        for t in templates
    ]
