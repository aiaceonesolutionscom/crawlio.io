import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_workspace, get_current_user_id, require_plan
from app.db.models.workspace import Workspace
from app.db.session import get_session
from app.schemas.email_account import (
    EmailAccountConnectResponse,
    EmailAccountRead,
    EmailAccountListResponse,
    EmailMessageRead,
    EmailMessagePageResponse,
    EmailQuotaRead,
)
from app.services import email_account_service, email_sync_service

router = APIRouter(prefix="/email-accounts", tags=["email-accounts"])


@router.get("/oauth/google/callback")
async def google_oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    session: AsyncSession = Depends(get_session),
):
    try:
        workspace_id, user_id = state.split(":")
        account = await email_account_service.connect_gmail_account(
            session, workspace_id, user_id, code
        )
        return EmailAccountRead.model_validate(account)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to connect Gmail: {exc}",
        )


@router.get("/connect/google", response_model=EmailAccountConnectResponse)
async def connect_google(
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    state = f"{workspace.id}:{user_id}"
    auth_url = await email_account_service.get_google_auth_url(state)
    return EmailAccountConnectResponse(auth_url=auth_url)


@router.get("", response_model=EmailAccountListResponse)
async def list_accounts(
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: AsyncSession = Depends(get_session),
):
    accounts = await email_account_service.list_email_accounts(session, workspace.id)
    return EmailAccountListResponse(
        items=[EmailAccountRead.model_validate(a) for a in accounts]
    )


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_account(
    account_id: str,
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: AsyncSession = Depends(get_session),
):
    account = await email_account_service.get_email_account(session, account_id)
    if not account or account.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    await email_account_service.disconnect_email_account(session, account_id)


@router.get("/{account_id}/quota", response_model=EmailQuotaRead)
async def get_quota(
    account_id: str,
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: AsyncSession = Depends(get_session),
):
    quota = await email_account_service.check_daily_quota(session, workspace.id, account_id)
    return EmailQuotaRead(**quota)


@router.get("/{account_id}/inbox", response_model=EmailMessagePageResponse)
async def get_inbox(
    account_id: str,
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: AsyncSession = Depends(get_session),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
):
    account = await email_account_service.get_email_account(session, account_id)
    if not account or account.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    messages, has_more = await email_sync_service.sync_inbox(session, account, page=page, page_size=page_size)
    return EmailMessagePageResponse(
        items=[EmailMessageRead(**m) for m in messages],
        page=page,
        page_size=page_size,
        has_more=has_more,
        total=len(messages),
    )


@router.get("/{account_id}/sent", response_model=EmailMessagePageResponse)
async def get_sent(
    account_id: str,
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: AsyncSession = Depends(get_session),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
):
    account = await email_account_service.get_email_account(session, account_id)
    if not account or account.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    messages, has_more = await email_sync_service.sync_sent(session, account, page=page, page_size=page_size)
    return EmailMessagePageResponse(
        items=[EmailMessageRead(**m) for m in messages],
        page=page,
        page_size=page_size,
        has_more=has_more,
        total=len(messages),
    )


@router.get("/{account_id}/trash", response_model=EmailMessagePageResponse)
async def get_trash(
    account_id: str,
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: AsyncSession = Depends(get_session),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
):
    account = await email_account_service.get_email_account(session, account_id)
    if not account or account.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    messages, has_more = await email_sync_service.sync_trash(session, account, page=page, page_size=page_size)
    return EmailMessagePageResponse(
        items=[EmailMessageRead(**m) for m in messages],
        page=page,
        page_size=page_size,
        has_more=has_more,
        total=len(messages),
    )


@router.get("/{account_id}/spam", response_model=EmailMessagePageResponse)
async def get_spam(
    account_id: str,
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: AsyncSession = Depends(get_session),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
):
    account = await email_account_service.get_email_account(session, account_id)
    if not account or account.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    messages, has_more = await email_sync_service.sync_spam(session, account, page=page, page_size=page_size)
    return EmailMessagePageResponse(
        items=[EmailMessageRead(**m) for m in messages],
        page=page,
        page_size=page_size,
        has_more=has_more,
        total=len(messages),
    )


@router.get("/{account_id}/messages/{message_id}")
async def get_message_detail(
    account_id: str,
    message_id: str,
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: AsyncSession = Depends(get_session),
):
    account = await email_account_service.get_email_account(session, account_id)
    if not account or account.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    message = await email_sync_service.get_email_detail(session, account, message_id)
    return EmailMessageRead(**message)


@router.post("/{account_id}/sync")
async def sync_account(
    account_id: str,
    workspace: Annotated[Workspace, Depends(require_plan("email_agent"))],
    session: AsyncSession = Depends(get_session),
):
    account = await email_account_service.get_email_account(session, account_id)
    if not account or account.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    from datetime import datetime, timezone
    account.last_synced_at = datetime.now(timezone.utc)
    await session.commit()

    return {"status": "synced", "last_synced_at": account.last_synced_at.isoformat()}
