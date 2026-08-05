from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_workspace, require_plan
from app.db.models.workspace import Workspace
from app.db.session import get_session
from app.schemas.lead import (
    LeadCreate,
    LeadEmailResponse,
    LeadListResponse,
    LeadRead,
    LeadUpdate,
    LeadWhatsAppResponse,
    lead_to_read,
)
from app.services import lead_service
from app.services.lead_service import DuplicateLeadError
from app.workers.tasks_scoring import score_lead_task

router = APIRouter(prefix="/leads", tags=["leads"])


def _duplicate_error(field: str) -> HTTPException:
    label = "email address" if field == "email" else "phone number"
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=f"A lead with this {label} already exists in your workspace",
    )


@router.get("", response_model=LeadListResponse)
async def list_leads(
    workspace: Annotated[Workspace, Depends(get_current_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
    search: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=25, ge=1, le=100),
):
    leads, total = await lead_service.list_leads(session, workspace.id, search, page=page, limit=limit)
    return LeadListResponse(
        items=[lead_to_read(lead) for lead in leads],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/export")
async def export_leads(
    workspace: Annotated[Workspace, Depends(require_plan("export"))],
    session: Annotated[AsyncSession, Depends(get_session)],
    search: Optional[str] = Query(default=None),
):
    csv_data = await lead_service.export_leads_csv(session, workspace.id, search)
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="leads-export.csv"'},
    )


@router.post("", response_model=LeadRead, status_code=status.HTTP_201_CREATED)
async def create_lead(
    payload: LeadCreate,
    workspace: Annotated[Workspace, Depends(get_current_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    try:
        lead = await lead_service.create_lead(session, workspace, payload)
    except DuplicateLeadError as exc:
        raise _duplicate_error(exc.field) from exc
    score_lead_task.delay(lead.id)
    return lead_to_read(lead)


@router.get("/{lead_id}", response_model=LeadRead)
async def get_lead(
    lead_id: str,
    workspace: Annotated[Workspace, Depends(get_current_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    lead = await lead_service.get_lead(session, workspace.id, lead_id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return lead_to_read(lead)


@router.patch("/{lead_id}", response_model=LeadRead)
async def update_lead(
    lead_id: str,
    payload: LeadUpdate,
    workspace: Annotated[Workspace, Depends(get_current_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    try:
        lead = await lead_service.update_lead(session, workspace.id, lead_id, payload)
    except DuplicateLeadError as exc:
        raise _duplicate_error(exc.field) from exc
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return lead_to_read(lead)


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lead(
    lead_id: str,
    workspace: Annotated[Workspace, Depends(get_current_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    deleted = await lead_service.delete_lead(session, workspace.id, lead_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")


@router.post("/{lead_id}/email", response_model=LeadEmailResponse)
async def send_lead_email(
    lead_id: str,
    workspace: Annotated[Workspace, Depends(get_current_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    try:
        await lead_service.send_lead_email(session, workspace, lead_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return LeadEmailResponse(sent=True)


@router.post("/{lead_id}/whatsapp", response_model=LeadWhatsAppResponse)
async def send_lead_whatsapp(
    lead_id: str,
    workspace: Annotated[Workspace, Depends(require_plan("whatsapp"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    _, url = await lead_service.record_whatsapp_outreach(session, workspace, lead_id)
    return LeadWhatsAppResponse(url=url)
