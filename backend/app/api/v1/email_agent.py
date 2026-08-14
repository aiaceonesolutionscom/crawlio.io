from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_workspace, require_plan
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


@router.post("/initialize", response_model=EmailConversationRead)
async def initialize_agent(
    input: EmailAgentInitializeRequest,
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: AsyncSession = Depends(get_session),
):
    conversation = await email_ai_service.initialize_agent_session(
        session=session,
        workspace_id=workspace.id,
        email_account_id=input.email_account_id,
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
    try:
        response = await email_ai_service.agent_collect_business_info(
            session=session,
            conversation_id=input.conversation_id,
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
    success = await resume_conversation(session, conversation_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return {"status": "resumed"}
