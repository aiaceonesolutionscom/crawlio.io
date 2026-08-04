from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.lead import Lead, LeadEvent
from app.db.models.workspace import Workspace
from app.schemas.lead import LeadCreate
from app.services.quota_service import check_lead_quota


async def list_leads(session: AsyncSession, workspace_id: str, search: Optional[str] = None) -> list[Lead]:
    query = select(Lead).where(Lead.workspace_id == workspace_id).order_by(Lead.created_at.desc())
    if search:
        like = f"%{search.lower()}%"
        query = query.where(
            func.lower(Lead.name).like(like) |
            func.lower(Lead.company).like(like) |
            func.lower(Lead.email).like(like)
        )
    result = await session.execute(query)
    return list(result.scalars().all())


async def create_lead(session: AsyncSession, workspace: Workspace, data: LeadCreate) -> Lead:
    await check_lead_quota(session, workspace)

    lead = Lead(
        workspace_id=workspace.id,
        name=data.name,
        company=data.company,
        email=data.email,
        phone=data.phone,
        source=data.source,
        lead_metadata=data.lead_metadata,
        status="New"
    )
    session.add(lead)
    await session.flush()

    event = LeadEvent(
        lead_id=lead.id,
        workspace_id=workspace.id,
        type="created",
        message=f"Lead {lead.name} captured from {lead.source or 'manual entry'}"
    )
    session.add(event)
    await session.commit()
    await session.refresh(lead)
    return lead


async def apply_score(session: AsyncSession, lead_id: str, score: int, status_label: str) -> Optional[Lead]:
    result = await session.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if lead is None:
        return None

    lead.score = score
    lead.status = status_label
    event = LeadEvent(
        lead_id=lead.id,
        workspace_id=lead.workspace_id,
        type="scored",
        message=f"AI scored this lead {score}/100"
    )
    session.add(event)
    await session.commit()
    await session.refresh(lead)
    return lead
