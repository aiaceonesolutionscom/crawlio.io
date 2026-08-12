import json
from typing import Annotated, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_workspace, require_plan
from app.db.models.workspace import Workspace
from app.db.session import get_session
from app.schemas.email_account import (
    ConversationStartRequest,
    ConversationMessageRequest,
    BookingRequest,
    BusinessInfoRequest,
    EmailConversationRead,
    EmailConversationMessageRead,
    ConversationListResponse,
    ConversationPreviewListResponse,
    ConversationWithMessages,
    CSVExportResponse,
    EmailQuotaRead,
)
from app.services import email_conversation_service, email_account_service

router = APIRouter(prefix="/email-conversations", tags=["email-conversations"])


@router.post("/start", response_model=EmailConversationRead)
async def start_conversation(
    input: ConversationStartRequest,
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: AsyncSession = Depends(get_session),
):
    account = await email_account_service.get_email_account(session, input.email_account_id)
    if not account or account.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email account not found")

    conv = await email_conversation_service.start_conversation(
        session, workspace.id, input.email_account_id,
        input.email_id, input.lead_name, input.lead_email, input.thread_id
    )
    return EmailConversationRead.model_validate(conv)


@router.post("/{conversation_id}/messages", response_model=EmailConversationMessageRead)
async def send_message(
    conversation_id: str,
    input: ConversationMessageRequest,
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: AsyncSession = Depends(get_session),
):
    from sqlalchemy import select
    from app.db.models.email_account import EmailConversation
    result = await session.execute(
        select(EmailConversation).where(
            EmailConversation.id == conversation_id,
            EmailConversation.workspace_id == workspace.id
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    msg = await email_conversation_service.send_conversation_message(
        session, conversation_id, input.message, input.sender_type
    )
    return EmailConversationMessageRead.model_validate(msg)


@router.post("/{conversation_id}/reply", response_model=dict)
async def send_manual_reply(
    conversation_id: str,
    input: ConversationMessageRequest,
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: AsyncSession = Depends(get_session),
):
    from sqlalchemy import select
    from app.db.models.email_account import EmailConversation
    result = await session.execute(
        select(EmailConversation).where(
            EmailConversation.id == conversation_id,
            EmailConversation.workspace_id == workspace.id
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    try:
        return await email_conversation_service.send_reply_email(
            session, conversation_id, input.message
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/{conversation_id}/stop")
async def stop_conversation(
    conversation_id: str,
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: AsyncSession = Depends(get_session),
):
    success = await email_conversation_service.stop_conversation(session, conversation_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return {"status": "stopped"}


@router.post("/{conversation_id}/resume")
async def resume_conversation(
    conversation_id: str,
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: AsyncSession = Depends(get_session),
):
    success = await email_conversation_service.resume_conversation(session, conversation_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return {"status": "resumed"}


@router.get("/{conversation_id}", response_model=ConversationWithMessages)
async def get_conversation(
    conversation_id: str,
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: AsyncSession = Depends(get_session),
):
    from sqlalchemy import func, select
    from app.db.models.email_account import EmailConversation, EmailConversationMessage
    from app.services.email_conversation_service import clean_message_content
    result = await session.execute(
        select(EmailConversation).where(
            EmailConversation.id == conversation_id,
            EmailConversation.workspace_id == workspace.id
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    msg_result = await session.execute(
        select(EmailConversationMessage).where(
            EmailConversationMessage.conversation_id == conversation_id
        ).order_by(func.coalesce(EmailConversationMessage.sent_at, EmailConversationMessage.created_at))
    )
    messages = list(msg_result.scalars().all())
    for m in messages:
        m.content = clean_message_content(m.content)

    return ConversationWithMessages(
        conversation=EmailConversationRead.model_validate(conv),
        messages=[EmailConversationMessageRead.model_validate(m) for m in messages]
    )


@router.post("/book-meeting", response_model=dict)
async def book_meeting(
    input: BookingRequest,
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: AsyncSession = Depends(get_session),
):
    result = await email_conversation_service.book_meeting(
        session, workspace.id, input.conversation_id,
        input.lead_name, input.lead_email, input.lead_company,
        input.meeting_datetime
    )
    return result


@router.post("/{conversation_id}/business-info", response_model=dict)
async def save_business_info(
    conversation_id: str,
    input: BusinessInfoRequest,
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: AsyncSession = Depends(get_session),
):
    from sqlalchemy import select, text
    from app.db.models.email_account import EmailConversation
    result = await session.execute(
        select(EmailConversation).where(
            EmailConversation.id == conversation_id,
            EmailConversation.workspace_id == workspace.id
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    business_context = {
        "business_name": input.business_name,
        "business_subject": input.business_subject,
        "business_additional_info": input.business_additional_info,
    }
    conv.business_context = json.dumps(business_context)
    conv.updated_at = datetime.now(timezone.utc)
    await session.commit()

    return {"status": "saved", "business_context": business_context}


@router.get("/accounts/{account_id}/active", response_model=ConversationListResponse)
async def get_active_conversations(
    account_id: str,
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: AsyncSession = Depends(get_session),
):
    conversations = await email_conversation_service.get_active_conversations(
        session, workspace.id, account_id
    )
    return ConversationListResponse(
        items=[EmailConversationRead.model_validate(c) for c in conversations]
    )


@router.get("/accounts/{account_id}/preview", response_model=ConversationPreviewListResponse)
async def conversation_previews(
    account_id: str,
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: AsyncSession = Depends(get_session),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
):
    """One clean WhatsApp-style row per customer conversation (latest message only)."""
    account = await email_account_service.get_email_account(session, account_id)
    if not account or account.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    items, total, has_more = await email_conversation_service.list_conversation_previews(
        session, account_id, page=page, page_size=page_size
    )
    return ConversationPreviewListResponse(
        items=items,
        page=page,
        page_size=page_size,
        has_more=has_more,
        total=total,
    )


@router.get("/booked-leads/export")
async def export_booked_leads(
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: AsyncSession = Depends(get_session),
):
    csv_content = await email_conversation_service.export_booked_leads_csv(
        session, workspace.id
    )
    response = Response(content=csv_content, media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=booked_leads.csv"
    return response


@router.get("/accounts/{account_id}/quota", response_model=EmailQuotaRead)
async def get_quota(
    account_id: str,
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: AsyncSession = Depends(get_session),
):
    quota = await email_account_service.check_daily_quota(session, workspace.id, account_id)
    return EmailQuotaRead(**quota)
