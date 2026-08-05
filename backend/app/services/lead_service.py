import csv
import io
import re
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.lead import Lead, LeadEvent
from app.db.models.workspace import Workspace
from app.schemas.lead import LeadCreate, LeadUpdate
from app.services import email_service
from app.services.quota_service import check_lead_quota


class DuplicateLeadError(Exception):
    def __init__(self, field: str):
        self.field = field


def _search_filter(query, search: str):
    like = f"%{search.lower()}%"
    return query.where(
        func.lower(Lead.name).like(like)
        | func.lower(Lead.company).like(like)
        | func.lower(Lead.email).like(like)
    )


async def _count_leads(session: AsyncSession, workspace_id: str, search: Optional[str] = None) -> int:
    query = select(func.count()).select_from(Lead).where(Lead.workspace_id == workspace_id)
    if search:
        query = _search_filter(query, search)
    result = await session.execute(query)
    return int(result.scalar_one())


async def list_leads(
    session: AsyncSession,
    workspace_id: str,
    search: Optional[str] = None,
    *,
    page: int = 1,
    limit: int = 25,
) -> tuple[list[Lead], int]:
    page = max(page, 1)
    limit = min(max(limit, 1), 100)
    offset = (page - 1) * limit

    query = select(Lead).where(Lead.workspace_id == workspace_id).order_by(Lead.created_at.desc())
    if search:
        query = _search_filter(query, search)
    query = query.offset(offset).limit(limit)

    result = await session.execute(query)
    items = list(result.scalars().all())
    total = await _count_leads(session, workspace_id, search)
    return items, total


async def get_lead(session: AsyncSession, workspace_id: str, lead_id: str) -> Optional[Lead]:
    result = await session.execute(
        select(Lead).where(Lead.id == lead_id, Lead.workspace_id == workspace_id)
    )
    return result.scalar_one_or_none()


async def _find_duplicate(
    session: AsyncSession,
    workspace_id: str,
    email: Optional[str],
    phone: Optional[str],
    exclude_id: Optional[str] = None,
) -> Optional[str]:
    if email:
        query = select(Lead).where(
            Lead.workspace_id == workspace_id,
            func.lower(Lead.email) == email.lower(),
        )
        if exclude_id:
            query = query.where(Lead.id != exclude_id)
        result = await session.execute(query)
        if result.scalar_one_or_none():
            return "email"

    if phone:
        normalized = re.sub(r"\s+", "", phone)
        query = select(Lead).where(Lead.workspace_id == workspace_id, Lead.phone == normalized)
        if exclude_id:
            query = query.where(Lead.id != exclude_id)
        result = await session.execute(query)
        if result.scalar_one_or_none():
            return "phone"

    return None


async def create_lead(session: AsyncSession, workspace: Workspace, data: LeadCreate) -> Lead:
    await check_lead_quota(session, workspace)

    duplicate = await _find_duplicate(session, workspace.id, data.email, data.phone)
    if duplicate:
        raise DuplicateLeadError(duplicate)

    phone = re.sub(r"\s+", "", data.phone) if data.phone else None

    lead = Lead(
        workspace_id=workspace.id,
        name=data.name,
        company=data.company,
        email=data.email,
        phone=phone,
        website=data.website,
        address=data.address,
        source=data.source,
        lead_metadata=data.lead_metadata,
        status="New",
    )
    session.add(lead)
    await session.flush()

    event = LeadEvent(
        lead_id=lead.id,
        workspace_id=workspace.id,
        type="created",
        message=f"Lead {lead.name} captured from {lead.source or 'manual entry'}",
    )
    session.add(event)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        duplicate = await _find_duplicate(session, workspace.id, data.email, data.phone)
        raise DuplicateLeadError(duplicate or "email")
    await session.refresh(lead)
    return lead


async def update_lead(
    session: AsyncSession, workspace_id: str, lead_id: str, data: LeadUpdate
) -> Optional[Lead]:
    lead = await get_lead(session, workspace_id, lead_id)
    if lead is None:
        return None

    updates = data.model_dump(exclude_unset=True)
    new_email = updates.get("email", lead.email)
    new_phone = updates.get("phone", lead.phone)
    if "phone" in updates and updates["phone"]:
        updates["phone"] = re.sub(r"\s+", "", updates["phone"])

    duplicate = await _find_duplicate(session, workspace_id, new_email, new_phone, exclude_id=lead_id)
    if duplicate:
        raise DuplicateLeadError(duplicate)

    for field, value in updates.items():
        setattr(lead, field, value)

    event = LeadEvent(
        lead_id=lead.id,
        workspace_id=workspace_id,
        type="updated",
        message=f"Lead {lead.name} updated",
    )
    session.add(event)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        duplicate = await _find_duplicate(session, workspace_id, new_email, new_phone, exclude_id=lead_id)
        raise DuplicateLeadError(duplicate or "email")
    await session.refresh(lead)
    return lead


async def delete_lead(session: AsyncSession, workspace_id: str, lead_id: str) -> bool:
    lead = await get_lead(session, workspace_id, lead_id)
    if lead is None:
        return False
    await session.delete(lead)
    await session.commit()
    return True


async def send_lead_email(session: AsyncSession, workspace: Workspace, lead_id: str) -> Lead:
    lead = await get_lead(session, workspace.id, lead_id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    if not lead.email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Lead has no email address")

    subject = f"Following up — {workspace.name}"
    html = email_service.lead_outreach_html(lead.name, workspace.name)
    await email_service.send_email(lead.email, subject, html)

    event = LeadEvent(
        lead_id=lead.id,
        workspace_id=workspace.id,
        type="email_sent",
        message=f"Outreach email sent to {lead.email}",
    )
    session.add(event)
    if lead.status == "New":
        lead.status = "Contacted"
    await session.commit()
    await session.refresh(lead)
    return lead


def whatsapp_url_for_lead(lead: Lead, workspace_name: str) -> str:
    if not lead.phone:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Lead has no phone number")
    digits = re.sub(r"\D", "", lead.phone)
    if not digits:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Lead phone number is invalid")
    message = f"Hi {lead.name}, following up from {workspace_name}."
    from urllib.parse import quote

    return f"https://wa.me/{digits}?text={quote(message)}"


async def record_whatsapp_outreach(session: AsyncSession, workspace: Workspace, lead_id: str) -> tuple[Lead, str]:
    lead = await get_lead(session, workspace.id, lead_id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    url = whatsapp_url_for_lead(lead, workspace.name)
    event = LeadEvent(
        lead_id=lead.id,
        workspace_id=workspace.id,
        type="whatsapp_sent",
        message=f"WhatsApp outreach opened for {lead.phone}",
    )
    session.add(event)
    if lead.status == "New":
        lead.status = "Contacted"
    await session.commit()
    await session.refresh(lead)
    return lead, url


async def export_leads_csv(
    session: AsyncSession, workspace_id: str, search: Optional[str] = None
) -> str:
    query = select(Lead).where(Lead.workspace_id == workspace_id).order_by(Lead.created_at.desc())
    if search:
        query = _search_filter(query, search)
    result = await session.execute(query)
    leads = list(result.scalars().all())

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["id", "name", "company", "email", "phone", "website", "address", "score", "status", "source", "created_at"]
    )
    for lead in leads:
        writer.writerow([
            lead.id,
            lead.name,
            lead.company or "",
            lead.email or "",
            lead.phone or "",
            lead.website or "",
            lead.address or "",
            lead.score if lead.score is not None else "",
            lead.status,
            lead.source or "",
            lead.created_at.isoformat(),
        ])
    return buffer.getvalue()


async def apply_score(session: AsyncSession, lead_id: str, score: int, status_label: str) -> Optional[Lead]:
    result = await session.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if lead is None:
        return None

    lead.score = score
    lead.status = status_label
    metadata = dict(lead.lead_metadata or {})
    metadata.pop("scoring_failed", None)
    lead.lead_metadata = metadata
    event = LeadEvent(
        lead_id=lead.id,
        workspace_id=lead.workspace_id,
        type="scored",
        message=f"AI scored this lead {score}/100",
    )
    session.add(event)
    await session.commit()
    await session.refresh(lead)
    return lead


async def mark_scoring_failed(session: AsyncSession, lead_id: str) -> None:
    result = await session.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if lead is None:
        return

    metadata = dict(lead.lead_metadata or {})
    metadata["scoring_failed"] = True
    lead.lead_metadata = metadata
    event = LeadEvent(
        lead_id=lead.id,
        workspace_id=lead.workspace_id,
        type="scoring_failed",
        message="AI scoring failed after retries",
    )
    session.add(event)
    await session.commit()
