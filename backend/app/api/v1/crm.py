from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_plan
from app.db.session import get_session
from app.db.models.workspace import Workspace
from app.schemas.crm import CrmAddRequest, CrmAddResult, CrmEntryListResponse, CrmEntryRead, CrmImportFromConversationRequest
from app.schemas.lead import lead_to_read
from app.services.crm import crm_service

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


@router.post("/import-email-conversation")
async def import_email_conversation(
    payload: CrmImportFromConversationRequest,
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    """Import a conversation from the email agent into the CRM as a lead."""
    from app.db.models.lead import Lead
    import uuid

    lead = Lead(
        id=str(uuid.uuid4()),
        workspace_id=workspace.id,
        name=payload.lead_name,
        email=payload.lead_email,
        company=payload.lead_company,
        source="email_agent",
        status="new",
    )
    session.add(lead)
    await session.commit()
    await session.refresh(lead)

    return {"lead_id": lead.id, "message": f"Imported conversation to CRM as lead {lead.email}"}
