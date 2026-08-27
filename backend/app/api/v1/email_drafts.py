from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_workspace, require_plan
from app.db.models.email_account import EmailAccount, EmailDraft
from app.db.models.workspace import Workspace
from app.db.session import get_session
from app.schemas.email_account import (
    EmailDraftCreate,
    EmailDraftRead,
    EmailDraftListResponse,
    EmailDraftUpdate,
)
from app.services.automation import email_compose_service

router = APIRouter(prefix="/email-drafts", tags=["email-drafts"])


async def _owned_draft_id(session: AsyncSession, draft_id: str, workspace_id: str) -> str:
    """Confirm `draft_id` belongs to the caller's workspace — without this, any
    workspace could update, send, or archive any other workspace's draft by
    guessing/observing its id."""
    result = await session.execute(
        select(EmailDraft.id).where(EmailDraft.id == draft_id, EmailDraft.workspace_id == workspace_id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    return draft_id


@router.post("", response_model=EmailDraftRead, status_code=status.HTTP_201_CREATED)
async def create_draft(
    input: EmailDraftCreate,
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: AsyncSession = Depends(get_session),
):
    account_result = await session.execute(
        select(EmailAccount.id).where(
            EmailAccount.id == input.email_account_id, EmailAccount.workspace_id == workspace.id
        )
    )
    if account_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email account not found")

    draft = await email_compose_service.create_draft(
        session=session,
        workspace_id=workspace.id,
        email_account_id=input.email_account_id,
        subject=input.subject,
        body=input.body,
        kind=input.kind,
        recipient_emails=input.recipient_emails,
        lead_id=input.lead_id,
        ai_prompt=input.ai_prompt,
        conversation_id=input.conversation_id,
    )
    return EmailDraftRead.model_validate(draft)


@router.get("", response_model=EmailDraftListResponse)
async def list_drafts(
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: AsyncSession = Depends(get_session),
    status_filter: Optional[str] = None,
):
    drafts = await email_compose_service.list_drafts(session, workspace.id, status_filter)
    return EmailDraftListResponse(
        items=[EmailDraftRead.model_validate(d) for d in drafts]
    )


@router.patch("/{draft_id}", response_model=EmailDraftRead)
async def update_draft(
    draft_id: str,
    input: EmailDraftUpdate,
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: AsyncSession = Depends(get_session),
):
    draft_id = await _owned_draft_id(session, draft_id, workspace.id)
    draft = await email_compose_service.update_draft(
        session=session,
        draft_id=draft_id,
        subject=input.subject,
        body=input.body,
        recipient_emails=input.recipient_emails,
    )
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    return EmailDraftRead.model_validate(draft)


@router.post("/{draft_id}/send")
async def send_draft(
    draft_id: str,
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: AsyncSession = Depends(get_session),
):
    draft_id = await _owned_draft_id(session, draft_id, workspace.id)
    try:
        email_message = await email_compose_service.send_draft(session, draft_id)
        if not email_message:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
        return {"status": "sent", "email_message_id": email_message.id}
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc))


@router.delete("/{draft_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_draft(
    draft_id: str,
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: AsyncSession = Depends(get_session),
):
    draft_id = await _owned_draft_id(session, draft_id, workspace.id)
    success = await email_compose_service.archive_draft(session, draft_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
