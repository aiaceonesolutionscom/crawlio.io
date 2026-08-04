from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_workspace
from app.db.models.workspace import Workspace
from app.db.session import get_session
from app.schemas.lead import LeadCreate, LeadListResponse, LeadRead
from app.services import lead_service
from app.workers.tasks_scoring import score_lead_task

router = APIRouter(prefix="/leads", tags=["leads"])


@router.get("", response_model=LeadListResponse)
async def list_leads(
    workspace: Annotated[Workspace, Depends(get_current_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)],
    search: Optional[str] = Query(default=None)
):
    leads = await lead_service.list_leads(session, workspace.id, search)
    return LeadListResponse(items=leads, total=len(leads))


@router.post("", response_model=LeadRead, status_code=status.HTTP_201_CREATED)
async def create_lead(
    payload: LeadCreate,
    workspace: Annotated[Workspace, Depends(get_current_workspace)],
    session: Annotated[AsyncSession, Depends(get_session)]
):
    lead = await lead_service.create_lead(session, workspace, payload)
    score_lead_task.delay(lead.id)
    return lead
