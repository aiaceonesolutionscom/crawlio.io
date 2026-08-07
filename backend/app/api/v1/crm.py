from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_plan
from app.db.session import get_session
from app.db.models.workspace import Workspace
from app.schemas.crm import CrmAddRequest, CrmAddResult, CrmEntryListResponse, CrmEntryRead
from app.schemas.lead import lead_to_read
from app.services import crm_service

router = APIRouter(prefix="/crm", tags=["crm"])


@router.get("/entries", response_model=CrmEntryListResponse)
async def list_crm_entries(
    workspace: Annotated[Workspace, Depends(require_plan("ai_lead_filter"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    entries = await crm_service.list_crm_entries(session, workspace.id)
    items = [
        CrmEntryRead(id=e.id, lead=lead_to_read(e.lead), category=e.category, added_at=e.added_at)
        for e in entries
    ]
    return CrmEntryListResponse(items=items, total=len(items))


@router.post("/entries", response_model=CrmAddResult)
async def add_to_crm(
    payload: CrmAddRequest,
    workspace: Annotated[Workspace, Depends(require_plan("ai_lead_filter"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    added, skipped = await crm_service.add_to_crm(session, workspace.id, payload.lead_ids)
    return CrmAddResult(added=added, skipped=skipped)
