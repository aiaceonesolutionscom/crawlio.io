from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_workspace, require_plan
from app.db.models.email_account import EmailAccount, EmailConversation
from app.db.models.workspace import Workspace
from app.db.session import get_session
from app.schemas.email_account import (
    EmailConversationRead,
    EmailConversationMessageRead,
    EmailAgentInitializeRequest,
    EmailAgentMessageRequest,
    EmailDraftRead,
)
from app.services.automation import email_ai_service
from app.services.automation.email_conversation_service import resume_conversation, stop_conversation

router = APIRouter(prefix="/email-agent", tags=["email-agent"])


async def _owned_account_id(session: AsyncSession, account_id: str, workspace_id: str) -> str:
    """Confirm `account_id` belongs to the caller's workspace before it's used
    for anything — without this, any workspace could act on any other
    workspace's connected Gmail account by guessing/observing its id."""
    result = await session.execute(
        select(EmailAccount.id).where(EmailAccount.id == account_id, EmailAccount.workspace_id == workspace_id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email account not found")
    return account_id


async def _owned_conversation_id(session: AsyncSession, conversation_id: str, workspace_id: str) -> str:
    """Same check as `_owned_account_id`, for conversation ids."""
    result = await session.execute(
        select(EmailConversation.id).where(
            EmailConversation.id == conversation_id, EmailConversation.workspace_id == workspace_id
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conversation_id


@router.post("/initialize", response_model=EmailConversationRead)
async def initialize_agent(
    input: EmailAgentInitializeRequest,
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: AsyncSession = Depends(get_session),
):
    email_account_id = await _owned_account_id(session, input.email_account_id, workspace.id)
    conversation = await email_ai_service.initialize_agent_session(
        session=session,
        workspace_id=workspace.id,
        email_account_id=email_account_id,
        lead_id=input.lead_id,
        subject=input.subject,
        lead_name=input.lead_name,
        lead_email=input.lead_email,
    )
    return EmailConversationRead.model_validate(conversation)


@router.post("/process-inbound/{account_id}")
async def process_inbound(
    account_id: str,
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: AsyncSession = Depends(get_session),
):
    """Sync-based auto-agent: fetch inbox and auto-respond to any new customer
    replies on active AI conversations. Called after an inbox refresh."""
    account_id = await _owned_account_id(session, account_id, workspace.id)
    try:
        result = await email_ai_service.process_inbound_replies_for_account(
            session, account_id
        )
        return result
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/message")
async def send_agent_message(
    input: EmailAgentMessageRequest,
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: AsyncSession = Depends(get_session),
):
    conversation_id = await _owned_conversation_id(session, input.conversation_id, workspace.id)
    try:
        response = await email_ai_service.agent_collect_business_info(
            session=session,
            conversation_id=conversation_id,
            user_input=input.message,
        )
        return {"response": response}
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/conversation/{conversation_id}", response_model=list[EmailConversationMessageRead])
async def get_conversation_history(
    conversation_id: str,
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: AsyncSession = Depends(get_session),
):
    conversation_id = await _owned_conversation_id(session, conversation_id, workspace.id)
    messages = await email_ai_service.get_agent_conversation_history(
        session, conversation_id
    )
    return [EmailConversationMessageRead.model_validate(m) for m in messages]


@router.post("/preview/{conversation_id}", response_model=EmailDraftRead)
async def preview_outreach(
    conversation_id: str,
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: AsyncSession = Depends(get_session),
):
    conversation_id = await _owned_conversation_id(session, conversation_id, workspace.id)
    try:
        draft = await email_ai_service.agent_generate_outreach(
            session, conversation_id
        )
        return EmailDraftRead.model_validate(draft)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/approve/{conversation_id}")
async def approve_outreach(
    conversation_id: str,
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: AsyncSession = Depends(get_session),
):
    conversation_id = await _owned_conversation_id(session, conversation_id, workspace.id)
    try:
        draft = await email_ai_service.agent_generate_outreach(
            session, conversation_id
        )
        result = await email_ai_service.approve_and_send_ai_email(session, draft.id)
        return {"status": "sent", "email_message_id": result.get("email_message_id")}
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/stop/{conversation_id}")
async def stop_agent(
    conversation_id: str,
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: AsyncSession = Depends(get_session),
):
    conversation_id = await _owned_conversation_id(session, conversation_id, workspace.id)
    success = await stop_conversation(session, conversation_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return {"status": "stopped"}


@router.post("/resume/{conversation_id}")
async def resume_agent(
    conversation_id: str,
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: AsyncSession = Depends(get_session),
):
    conversation_id = await _owned_conversation_id(session, conversation_id, workspace.id)
    success = await resume_conversation(session, conversation_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return {"status": "resumed"}
