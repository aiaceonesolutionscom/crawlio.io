from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_workspace, require_plan
from app.db.models.workspace import Workspace
from app.db.session import get_session
from app.schemas.email_account import (
    EmailAIGenerateRequest,
    EmailDraftRead,
)
from app.services.automation import email_ai_service

router = APIRouter(prefix="/email-ai", tags=["email-ai"])


@router.post("/generate", response_model=EmailDraftRead)
async def generate_email(
    input: EmailAIGenerateRequest,
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: AsyncSession = Depends(get_session),
):
    try:
        draft = await email_ai_service.generate_email_draft(
            session=session,
            workspace_id=workspace.id,
            email_account_id=input.email_account_id,
            prompt=input.prompt,
            lead_id=input.lead_id,
            lead_name=input.lead_name,
            lead_company=input.lead_company,
            lead_email=input.lead_email,
        )
        return EmailDraftRead.model_validate(draft)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post("/review/{draft_id}", response_model=EmailDraftRead)
async def review_ai_email(
    draft_id: str,
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: AsyncSession = Depends(get_session),
):
    from sqlalchemy import select
    from app.db.models.email_account import EmailDraft

    result = await session.execute(select(EmailDraft).where(EmailDraft.id == draft_id))
    draft = result.scalar_one_or_none()
    if not draft or draft.kind != "ai_generated":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI draft not found")
    return EmailDraftRead.model_validate(draft)


@router.post("/approve/{draft_id}")
async def approve_ai_email(
    draft_id: str,
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: AsyncSession = Depends(get_session),
):
    result = await email_ai_service.approve_and_send_ai_email(session, draft_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI draft not found")
    return {"status": "sent", "email_message_id": result.get("email_message_id")}
