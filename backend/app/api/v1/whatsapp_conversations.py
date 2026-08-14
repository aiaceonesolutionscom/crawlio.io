from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_plan
from app.db.models.workspace import Workspace
from app.db.models.whatsapp import WhatsAppConversation, WhatsAppConversationMessage
from app.db.session import get_session
from app.schemas.whatsapp_conversation import (
    WhatsAppBookingRequest,
    WhatsAppBusinessInfoRequest,
    WhatsAppConversationListResponse,
    WhatsAppConversationMessageRead,
    WhatsAppConversationPreviewListResponse,
    WhatsAppConversationRead,
    WhatsAppConversationWithMessages,
    WhatsAppStatsRead,
)
from app.services.whatsapp import whatsapp_conversation_service as svc
from app.services.whatsapp import whatsapp_account_service

router = APIRouter(prefix="/whatsapp-conversations", tags=["whatsapp-conversations"])


@router.get("/accounts/{account_id}/active", response_model=WhatsAppConversationListResponse)
async def get_active(
    account_id: str,
    workspace: Annotated[Workspace, Depends(require_plan("whatsapp"))],
    session: AsyncSession = Depends(get_session),
):
    account = await whatsapp_account_service.get_whatsapp_account(session, account_id)
    if not account or account.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    conversations = await svc.get_active_conversations(session, workspace.id, account_id)
    return WhatsAppConversationListResponse(
        items=[WhatsAppConversationRead.model_validate(c) for c in conversations]
    )


@router.get("/accounts/{account_id}/preview", response_model=WhatsAppConversationPreviewListResponse)
async def get_previews(
    account_id: str,
    workspace: Annotated[Workspace, Depends(require_plan("whatsapp"))],
    session: AsyncSession = Depends(get_session),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
):
    account = await whatsapp_account_service.get_whatsapp_account(session, account_id)
    if not account or account.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    items, total, has_more = await svc.list_conversation_previews(
        session, account_id, page=page, page_size=page_size
    )
    return WhatsAppConversationPreviewListResponse(
        items=items, page=page, page_size=page_size, has_more=has_more, total=total
    )


@router.get("/{conversation_id}", response_model=WhatsAppConversationWithMessages)
async def get_conversation(
    conversation_id: str,
    workspace: Annotated[Workspace, Depends(require_plan("whatsapp"))],
    session: AsyncSession = Depends(get_session),
):
    conv = await svc.get_conversation(session, conversation_id)
    if not conv or conv.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    msg_result = await session.execute(
        select(WhatsAppConversationMessage)
        .where(WhatsAppConversationMessage.conversation_id == conversation_id)
        .order_by(WhatsAppConversationMessage.created_at.asc())
    )
    messages = list(msg_result.scalars().all())
    return WhatsAppConversationWithMessages(
        conversation=WhatsAppConversationRead.model_validate(conv),
        messages=[WhatsAppConversationMessageRead.model_validate(m) for m in messages],
    )


@router.post("/{conversation_id}/messages", response_model=WhatsAppConversationMessageRead)
async def add_message(
    conversation_id: str,
    payload: dict,
    workspace: Annotated[Workspace, Depends(require_plan("whatsapp"))],
    session: AsyncSession = Depends(get_session),
):
    conv = await svc.get_conversation(session, conversation_id)
    if not conv or conv.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    msg = await svc.send_conversation_message(
        session,
        conversation_id,
        payload.get("message", ""),
        sender_type=payload.get("sender_type", "user"),
    )
    return WhatsAppConversationMessageRead.model_validate(msg)


@router.post("/{conversation_id}/reply")
async def reply_message(
    conversation_id: str,
    payload: dict,
    workspace: Annotated[Workspace, Depends(require_plan("whatsapp"))],
    session: AsyncSession = Depends(get_session),
):
    """Manual real reply (user takes over the chat)."""
    conv = await svc.get_conversation(session, conversation_id)
    if not conv or conv.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    try:
        result = await svc.send_reply_message(
            session, conversation_id, payload.get("message", ""), sender_type="user"
        )
        return result
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/{conversation_id}/stop")
async def stop_agent(
    conversation_id: str,
    workspace: Annotated[Workspace, Depends(require_plan("whatsapp"))],
    session: AsyncSession = Depends(get_session),
):
    success = await svc.stop_conversation(session, conversation_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return {"status": "stopped"}


@router.post("/{conversation_id}/resume")
async def resume_agent(
    conversation_id: str,
    workspace: Annotated[Workspace, Depends(require_plan("whatsapp"))],
    session: AsyncSession = Depends(get_session),
):
    success = await svc.resume_conversation(session, conversation_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return {"status": "resumed"}


@router.post("/book-meeting")
async def book_meeting(
    payload: WhatsAppBookingRequest,
    workspace: Annotated[Workspace, Depends(require_plan("whatsapp"))],
    session: AsyncSession = Depends(get_session),
):
    """Manual booking (the human books for a customer directly)."""
    try:
        result = await svc.book_meeting(
            session,
            workspace.id,
            payload.conversation_id,
            payload.lead_name,
            payload.lead_phone,
            payload.lead_company,
            payload.meeting_datetime,
        )
        return result
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/{conversation_id}/business-info")
async def save_business_info(
    conversation_id: str,
    payload: WhatsAppBusinessInfoRequest,
    workspace: Annotated[Workspace, Depends(require_plan("whatsapp"))],
    session: AsyncSession = Depends(get_session),
):
    conv = await svc.get_conversation(session, conversation_id)
    if not conv or conv.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    try:
        result = await svc.save_business_info(
            session,
            conversation_id,
            payload.business_name,
            payload.business_subject,
            payload.business_additional_info,
        )
        return result
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/booked-leads/export")
async def export_booked_leads(
    workspace: Annotated[Workspace, Depends(require_plan("whatsapp"))],
    session: AsyncSession = Depends(get_session),
):
    csv_content = await svc.export_booked_leads_csv(session, workspace.id)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=whatsapp-booked-leads.csv"},
    )


@router.get("/accounts/{account_id}/stats", response_model=WhatsAppStatsRead)
async def get_stats(
    account_id: str,
    workspace: Annotated[Workspace, Depends(require_plan("whatsapp"))],
    session: AsyncSession = Depends(get_session),
):
    account = await whatsapp_account_service.get_whatsapp_account(session, account_id)
    if not account or account.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    from datetime import datetime, timezone
    from sqlalchemy import and_

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    async def count(predicate) -> int:
        return (await session.execute(select(sa_func.count()).select_from(WhatsAppConversationMessage).where(predicate))).scalar() or 0

    conv_ids = [c.id for c in (await session.execute(
        select(WhatsAppConversation).where(WhatsAppConversation.whatsapp_account_id == account_id)
    )).scalars().all()]

    if not conv_ids:
        return WhatsAppStatsRead(outreach_sent_today=0, inbound_received_today=0, ai_replies_today=0, meetings_booked_today=0, active_conversations=0, total_messages_today=0)

    inbound = await count(and_(
        WhatsAppConversationMessage.conversation_id.in_(conv_ids),
        WhatsAppConversationMessage.direction == "inbound",
        WhatsAppConversationMessage.created_at >= today_start,
    ))
    ai_replies = await count(and_(
        WhatsAppConversationMessage.conversation_id.in_(conv_ids),
        WhatsAppConversationMessage.sender_type == "ai",
        WhatsAppConversationMessage.direction == "outbound",
        WhatsAppConversationMessage.created_at >= today_start,
    ))
    user_outbound = await count(and_(
        WhatsAppConversationMessage.conversation_id.in_(conv_ids),
        WhatsAppConversationMessage.sender_type == "user",
        WhatsAppConversationMessage.direction == "outbound",
        WhatsAppConversationMessage.created_at >= today_start,
    ))
    booked_today = await count(and_(
        WhatsAppConversationMessage.conversation_id.in_(conv_ids),
        WhatsAppConversationMessage.sender_type == "system",
        WhatsAppConversationMessage.content.like("Meeting booked!%"),
        WhatsAppConversationMessage.created_at >= today_start,
    ))

    active = (await session.execute(
        select(sa_func.count()).select_from(WhatsAppConversation).where(
            WhatsAppConversation.whatsapp_account_id == account_id,
            WhatsAppConversation.ai_agent_active.is_(True),
        )
    )).scalar() or 0

    return WhatsAppStatsRead(
        outreach_sent_today=user_outbound + ai_replies,
        inbound_received_today=inbound,
        ai_replies_today=ai_replies,
        meetings_booked_today=booked_today,
        active_conversations=active,
        total_messages_today=inbound + ai_replies + user_outbound,
    )