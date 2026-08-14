"""Agent hub API: persistent business profile, outreach selector + send,
meeting listing, and AI activity replay."""

from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_workspace, require_plan
from app.db.models.agent import BusinessProfile, Meeting
from app.db.models.lead import Lead
from app.db.models.workspace import Workspace
from app.db.session import get_session
from app.services.agent import agent_realtime, business_profile_service
from app.services.automation import meeting_service, outreach_service
from app.services.automation import email_account_service

router = APIRouter(tags=["agent"])


class BusinessProfileWrite(BaseModel):
    business_name: str
    owner_name: str
    business_phone: Optional[str] = None
    business_address: Optional[str] = None
    services: str = ""
    website: Optional[str] = None
    timezone: str = "Asia/Karachi"
    business_hours: Optional[dict] = None
    knowledge_base: str = ""


class BusinessProfileRead(BaseModel):
    id: str
    business_name: str
    owner_name: str
    business_phone: Optional[str] = None
    business_address: Optional[str] = None
    services: str
    website: Optional[str] = None
    timezone: str
    business_hours: dict
    knowledge_base: str
    updated_at: datetime


class EligibleLeadRead(BaseModel):
    lead_id: str
    name: str
    company: Optional[str] = None
    email: str
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
    current_subject: str = ""
    current_body: str = ""


class OutreachDraftRead(BaseModel):
    lead_id: str
    recipient_name: str = ""
    recipient_company: Optional[str] = None
    recipient_email: str = ""
    source: str
    subject: str
    body: str


class OutreachApproveItem(BaseModel):
    lead_id: str
    subject: str
    body: str


class OutreachApproveRequest(BaseModel):
    items: list[OutreachApproveItem]


class MeetingRead(BaseModel):
    id: str
    booking_ref: str
    lead_name: Optional[str] = None
    lead_email: Optional[str] = None
    scheduled_at: datetime
    status: str


class EditReplyRequest(BaseModel):
    reply: str


async def _find_lead(session: AsyncSession, workspace_id: str, lead_id: str) -> Lead:
    result = await session.execute(
        select(Lead).where(Lead.id == lead_id, Lead.workspace_id == workspace_id)
    )
    lead = result.scalar_one_or_none()
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return lead


@router.get("/business-profile", response_model=Optional[BusinessProfileRead])
async def get_business_profile(
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    profile = await business_profile_service.get_profile(session, workspace.id)
    if profile is None:
        return None
    return BusinessProfileRead(
        id=profile.id,
        business_name=profile.business_name,
        owner_name=profile.owner_name,
        business_phone=profile.business_phone,
        business_address=profile.business_address,
        services=profile.services,
        website=profile.website,
        timezone=profile.timezone,
        business_hours=profile.business_hours,
        knowledge_base=profile.knowledge_base,
        updated_at=profile.updated_at,
    )


@router.post("/business-profile", response_model=BusinessProfileRead, status_code=status.HTTP_201_CREATED)
async def create_business_profile(
    payload: BusinessProfileWrite,
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    existing = await business_profile_service.get_profile(session, workspace.id)
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Business profile already exists")
    profile = await business_profile_service.create_profile(
        session,
        workspace.id,
        business_name=payload.business_name,
        owner_name=payload.owner_name,
        business_phone=payload.business_phone,
        business_address=payload.business_address,
        services=payload.services,
        website=payload.website,
        timezone=payload.timezone,
        knowledge_base=payload.knowledge_base,
    )
    return BusinessProfileRead(
        id=profile.id,
        business_name=profile.business_name,
        owner_name=profile.owner_name,
        business_phone=profile.business_phone,
        business_address=profile.business_address,
        services=profile.services,
        website=profile.website,
        timezone=profile.timezone,
        business_hours=profile.business_hours,
        knowledge_base=profile.knowledge_base,
        updated_at=profile.updated_at,
    )


@router.put("/business-profile", response_model=BusinessProfileRead)
async def update_business_profile(
    payload: BusinessProfileWrite,
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    profile = await business_profile_service.get_profile(session, workspace.id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business profile not found")
    profile = await business_profile_service.update_profile(
        session,
        profile,
        business_name=payload.business_name,
        owner_name=payload.owner_name,
        business_phone=payload.business_phone,
        business_address=payload.business_address,
        services=payload.services,
        website=payload.website,
        timezone=payload.timezone,
        business_hours=payload.business_hours,
        knowledge_base=payload.knowledge_base,
    )
    return BusinessProfileRead(
        id=profile.id,
        business_name=profile.business_name,
        owner_name=profile.owner_name,
        business_phone=profile.business_phone,
        business_address=profile.business_address,
        services=profile.services,
        website=profile.website,
        timezone=profile.timezone,
        business_hours=profile.business_hours,
        knowledge_base=profile.knowledge_base,
        updated_at=profile.updated_at,
    )


@router.get("/outreach/usage", response_model=OutreachUsage)
async def get_outreach_usage(
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    profile = await business_profile_service.get_profile(session, workspace.id)
    tz = profile.timezone if profile else "Asia/Karachi"
    used = await outreach_service.outreach_used_today(session, workspace.id, tz)
    limit = outreach_service.outreach_daily_limit(workspace)
    return OutreachUsage(used=used, limit=limit, remaining=max(0, limit - used))


@router.get("/outreach/eligible-leads", response_model=list[EligibleLeadRead])
async def get_eligible_leads(
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    leads = await outreach_service.eligible_leads(session, workspace.id)
    return [
        EligibleLeadRead(
            lead_id=lead.id,
            name=lead.name,
            company=lead.company,
            email=lead.email,
            website=lead.website,
            source=outreach_service.lead_source(lead),
        )
        for lead in leads
    ]


@router.post("/outreach/generate", response_model=list[OutreachDraftRead])
async def generate_outreach(
    payload: OutreachGenerateRequest,
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    profile = await business_profile_service.get_profile(session, workspace.id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Set up your business profile first")
    if not payload.lead_ids:
        return []

    from sqlalchemy import select as sa_select

    result = await session.execute(
        sa_select(Lead).where(
            Lead.id.in_(payload.lead_ids),
            Lead.workspace_id == workspace.id,
        )
    )
    leads = list(result.scalars().all())
    ordered = [l for l in leads if l.id in payload.lead_ids]
    account = await outreach_service.get_sender_account(session, workspace.id)
    drafts = await outreach_service.generate_outreports(session, profile, ordered, account)
    return [OutreachDraftRead(**d) for d in drafts]


@router.post("/outreach/regenerate", response_model=OutreachDraftRead)
async def regenerate_outreach(
    payload: OutreachRegenerateRequest,
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    lead = await _find_lead(session, workspace.id, payload.lead_id)
    profile = await business_profile_service.get_profile(session, workspace.id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Set up your business profile first")

    # Re-run personalised generation (the LLM sees the recipient context again).
    account = await outreach_service.get_sender_account(session, workspace.id)
    drafts = await outreach_service.generate_outreports(session, profile, [lead], account)
    if not drafts:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Generation failed")
    draft = drafts[0]
    return OutreachDraftRead(**draft)


@router.post("/outreach/approve")
async def approve_outreach(
    payload: OutreachApproveRequest,
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    if not payload.items:
        return {"sent": 0, "rejected": 0, "results": []}

    profile = await business_profile_service.get_profile(session, workspace.id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Set up your business profile first")

    results = []
    sent = 0
    rejected = 0
    for item in payload.items:
        lead = await _find_lead(session, workspace.id, item.lead_id)
        try:
            outcome = await outreach_service.send_outreach(
                session, workspace, profile, lead, item.subject, item.body
            )
            await agent_realtime.publish_activity(
                session,
                workspace.id,
                "outreach_sent",
                conversation_id=None,
                detail=f"Outreach sent to {lead.email}",
            )
            sent += 1
            results.append({"lead_id": lead.id, "ok": True, **outcome})
        except RuntimeError as exc:
            rejected += 1
            results.append({"lead_id": lead.id, "ok": False, "error": str(exc)})
    await session.commit()
    return {"sent": sent, "rejected": rejected, "results": results}


@router.get("/meetings", response_model=list[MeetingRead])
async def list_meetings(
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        select(Meeting).where(Meeting.workspace_id == workspace.id).order_by(Meeting.scheduled_at.desc()).limit(50)
    )
    meetings = list(result.scalars().all())
    return [
        MeetingRead(
            id=m.id,
            booking_ref=m.booking_ref,
            lead_name=m.lead_name,
            lead_email=m.lead_email,
            scheduled_at=m.scheduled_at,
            status=m.status,
        )
        for m in meetings
    ]


@router.get("/agent/activity")
async def get_activity(
    workspace: Annotated[Workspace, Depends(get_current_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    activities = await agent_realtime.list_recent_activity(session, workspace.id, limit=100)
    return [
        {
            "id": a.id,
            "conversation_id": a.conversation_id,
            "whatsapp_conversation_id": a.whatsapp_conversation_id,
            "stage": a.stage,
            "status": a.status,
            "detail": a.detail,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in activities
    ]


@router.post("/conversations/{conversation_id}/edit-reply")
async def edit_and_send_reply(
    conversation_id: str,
    payload: EditReplyRequest,
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    from app.db.models.email_account import EmailConversation

    result = await session.execute(
        select(EmailConversation).where(
            EmailConversation.id == conversation_id,
            EmailConversation.workspace_id == workspace.id,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    if not conv.customer_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No customer email on this conversation")

    from app.db.models.email_account import EmailConversationMessage
    from app.services.automation import email_sync_service

    account = await email_account_service.get_email_account(session, conv.email_account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email account not found")

    subject = f"Re: {conv.subject}" if not conv.subject.startswith("Re:") else conv.subject
    await email_sync_service.send_email_from_account(session, account, conv.customer_email, subject, payload.reply)

    msg = EmailConversationMessage(
        conversation_id=conversation_id,
        sender_type="user",
        content=payload.reply,
        is_approved=True,
        sent_at=datetime.now(timezone.utc),
    )
    session.add(msg)
    conv.updated_at = datetime.now(timezone.utc)
    await session.commit()
    return {"status": "sent", "message": payload.reply}