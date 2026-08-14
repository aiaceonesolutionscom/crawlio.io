from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user_id, require_plan
from app.db.models.workspace import Workspace
from app.db.session import get_session
from app.schemas.whatsapp_account import (
    WhatsAppAccountListResponse,
    WhatsAppAccountRead,
    WhatsAppConnectResponse,
    WhatsAppManualConnectRequest,
    WhatsAppQuotaRead,
)
from app.services.whatsapp import whatsapp_account_service

router = APIRouter(prefix="/whatsapp-accounts", tags=["whatsapp-accounts"])


@router.get("/connect", response_model=WhatsAppConnectResponse)
async def connect_whatsapp(
    workspace: Annotated[Workspace, Depends(require_plan("whatsapp"))],
    user_id: Annotated[str, Depends(get_current_user_id)],
):
    """Return the connect target. When Meta app creds + webhook URL are set it
    returns an Embedded Signup OAuth URL; otherwise it advertises test-mode so
    the frontend shows the manual System User credentials form."""
    try:
        auth_url = await whatsapp_account_service.build_embedded_signup_url(
            f"{workspace.id}:{user_id}"
        )
        return WhatsAppConnectResponse(auth_url=auth_url, test_mode=False)
    except RuntimeError:
        return WhatsAppConnectResponse(auth_url=None, test_mode=True)


@router.get("/oauth/embedded/callback")
async def embedded_signup_callback(
    code: str,
    state: str,
    session: AsyncSession = Depends(get_session),
):
    """Embedded Signup callback: exchange code -> system-user token, auto-fill
    the WABA + phone numbers, create the account row. (Production path.)"""
    try:
        workspace_id, user_id = state.split(":")
        token_data = await whatsapp_account_service.exchange_embedded_signup_code(code)
        token = token_data.get("access_token")
        if not token:
            raise RuntimeError("No access_token in exchange response")
        phones = await whatsapp_account_service.get_system_user_phone_numbers(token)
        if not phones:
            raise RuntimeError("No phone numbers found on this WABA")
        first = phones[0]
        account = await whatsapp_account_service.connect_whatsapp_account(
            session,
            workspace_id,
            user_id,
            phone_number_id=first["phone_number_id"],
            access_token=token,
            waba_id=first.get("waba_id"),
            business_phone=first.get("business_phone"),
            display_name=first.get("display_name"),
            token_type="embedded_signup",
        )
        return WhatsAppAccountRead.model_validate(account)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to connect WhatsApp: {exc}",
        )


@router.post("/connect", response_model=WhatsAppAccountRead)
async def connect_manual(
    payload: WhatsAppManualConnectRequest,
    workspace: Annotated[Workspace, Depends(require_plan("whatsapp"))],
    user_id: Annotated[str, Depends(get_current_user_id)],
    session: AsyncSession = Depends(get_session),
):
    """Manual connect: user pastes phone_number_id + a permanent System User
    token (works before Embedded Signup / App Review). Runs a live validity
    check against the Graph API first."""
    valid = await whatsapp_account_service.is_token_valid(payload.access_token)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Access token invalid or expired",
        )
    try:
        await whatsapp_account_service.get_system_user_phone_numbers(payload.access_token)
    except Exception:
        pass
    account = await whatsapp_account_service.connect_whatsapp_account(
        session,
        workspace.id,
        user_id,
        phone_number_id=payload.phone_number_id,
        access_token=payload.access_token,
        waba_id=payload.waba_id,
        business_phone=payload.business_phone,
        display_name=payload.display_name,
    )
    return WhatsAppAccountRead.model_validate(account)


@router.get("", response_model=WhatsAppAccountListResponse)
async def list_accounts(
    workspace: Annotated[Workspace, Depends(require_plan("whatsapp"))],
    session: AsyncSession = Depends(get_session),
):
    accounts = await whatsapp_account_service.list_whatsapp_accounts(session, workspace.id)
    return WhatsAppAccountListResponse(
        items=[WhatsAppAccountRead.model_validate(a) for a in accounts]
    )


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_account(
    account_id: str,
    workspace: Annotated[Workspace, Depends(require_plan("whatsapp"))],
    session: AsyncSession = Depends(get_session),
):
    account = await whatsapp_account_service.get_whatsapp_account(session, account_id)
    if not account or account.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    await whatsapp_account_service.disconnect_whatsapp_account(session, account_id)


@router.get("/{account_id}/quota", response_model=WhatsAppQuotaRead)
async def get_quota(
    account_id: str,
    workspace: Annotated[Workspace, Depends(require_plan("whatsapp"))],
    session: AsyncSession = Depends(get_session),
):
    account = await whatsapp_account_service.get_whatsapp_account(session, account_id)
    if not account or account.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    quota = await whatsapp_account_service.check_daily_quota(
        session, workspace.id, account_id
    )
    return WhatsAppQuotaRead(**quota)