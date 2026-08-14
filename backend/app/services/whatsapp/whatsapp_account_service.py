"""WhatsApp account service: connect (manual/test creds + Embedded Signup),
list, disconnect, quota, token validity. Mirrors email_account_service.py.

Two connect paths both land in the SAME flow and produce identical rows:
  * Embedded Signup (production)  -> code exchange gives system-user token
  * Manual System User token      -> user pastes phone_number_id + token
Permanent tokens (Expire=Never) mean no reconnection is ever required unless
the user revokes the app in Meta themselves."""

from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.whatsapp import WhatsAppAccount


async def connect_whatsapp_account(
    session: AsyncSession,
    workspace_id: str,
    user_id: str,
    phone_number_id: str,
    access_token: str,
    waba_id: Optional[str] = None,
    business_phone: Optional[str] = None,
    display_name: Optional[str] = None,
    token_type: str = "system_user",
) -> WhatsAppAccount:
    """Persist a connected WhatsApp number. Used by both the manual
    credentials form and the Embedded Signup callback after token exchange."""
    account = WhatsAppAccount(
        workspace_id=workspace_id,
        user_id=user_id,
        phone_number_id=phone_number_id,
        waba_id=waba_id,
        business_phone=business_phone,
        display_name=display_name,
        access_token=access_token,
        token_type=token_type,
    )
    session.add(account)
    await session.commit()
    await session.refresh(account)
    return account


async def build_embedded_signup_url(state: str) -> str:
    """Meta Embedded Signup OAuth URL. Requires whatsapp_webhook_url to be set
    (Meta uses it for post-login redirect + permissions tracking)."""
    if not settings.meta_app_id:
        raise RuntimeError("META_APP_ID is not configured")
    redirect = settings.whatsapp_webhook_url.rstrip("/") + "/whatsapp-accounts/oauth/embedded/callback"
    token_url = (
        f"https://graph.facebook.com/{settings.whatsapp_graph_version or 'v21.0'}"
        "/whatsapp_business_management"
    )
    params = {
        "app_id": settings.meta_app_id,
        "state": state,
        "response_type": "code",
        "redirect_uri": redirect,
        "scope": "whatsapp_business_messaging whatsapp_business_management",
        "override_country_code": "US",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"https://secure.whatsapp.com/embedded/signup?{query}&context={token_url}"


async def exchange_embedded_signup_code(code: str) -> dict:
    """Exchange the Embedded Signup code for a system-user access token."""
    if not (settings.meta_app_id and settings.meta_app_secret):
        raise RuntimeError("META_APP_ID / META_APP_SECRET not configured")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://graph.facebook.com/v19.0/oauth/access_token",
            params={
                "client_id": settings.meta_app_id,
                "client_secret": settings.meta_app_secret,
                "code": code,
                "grant_type": "authorization_code",
            },
        )
        resp.raise_for_status()
        return resp.json()


async def get_system_user_phone_numbers(token: str) -> list[dict]:
    """Fetch the WABA + phone numbers owned by a system-user token, so the
    Embedded Signup callback can auto-fill waba_id and business_phone."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                "https://graph.facebook.com/v19.0/me/businesses",
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            data = resp.json()
        for business in data.get("data", []):
            waba_url = (
                f"https://graph.facebook.com/v19.0/{business.get('id')}"
                "/owned_whatsapp_business_accounts?fields=id,name,verified_name"
            )
            async with httpx.AsyncClient(timeout=30.0) as client:
                waba_resp = await client.get(
                    waba_url, headers={"Authorization": f"Bearer {token}"}
                )
                waba_resp.raise_for_status()
                waba_data = waba_resp.json()
            for waba in waba_data.get("data", []):
                phone_url = (
                    f"https://graph.facebook.com/v19.0/{waba.get('id')}/phone_numbers"
                    "?fields=id,display_phone_number,verified_name"
                )
                async with httpx.AsyncClient(timeout=30.0) as client:
                    phone_resp = await client.get(
                        phone_url, headers={"Authorization": f"Bearer {token}"}
                    )
                    phone_resp.raise_for_status()
                    phone_data = phone_resp.json()
                return [
                    {
                        "waba_id": waba.get("id"),
                        "waba_name": waba.get("name"),
                        "phone_number_id": p.get("id"),
                        "business_phone": p.get("display_phone_number"),
                        "display_name": p.get("verified_name"),
                    }
                    for p in phone_data.get("data", [])
                ]
    except Exception:
        return []
    return []


async def list_whatsapp_accounts(
    session: AsyncSession, workspace_id: str
) -> list[WhatsAppAccount]:
    result = await session.execute(
        select(WhatsAppAccount)
        .where(WhatsAppAccount.workspace_id == workspace_id)
        .order_by(WhatsAppAccount.created_at.desc())
    )
    return list(result.scalars().all())


async def get_whatsapp_account(
    session: AsyncSession, account_id: str
) -> Optional[WhatsAppAccount]:
    result = await session.execute(
        select(WhatsAppAccount).where(WhatsAppAccount.id == account_id)
    )
    return result.scalar_one_or_none()


async def disconnect_whatsapp_account(
    session: AsyncSession, account_id: str
) -> None:
    account = await get_whatsapp_account(session, account_id)
    if account:
        await session.delete(account)
        await session.commit()


async def is_token_valid(access_token: Optional[str]) -> bool:
    """Permanent tokens never expire, so validity = token present + Meta still
    accepts it. Called on connect and lazily on send failures (401 handling)."""
    if not access_token:
        return False
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                "https://graph.facebook.com/v19.0/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            return resp.status_code == 200
    except Exception:
        return False


async def check_daily_quota(
    session: AsyncSession, workspace_id: str, whatsapp_account_id: str
) -> dict:
    from app.db.models.workspace import Workspace

    result = await session.execute(
        select(WhatsAppAccount).where(WhatsAppAccount.id == whatsapp_account_id)
    )
    account = result.scalar_one_or_none()
    ws_result = await session.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = ws_result.scalar_one_or_none()
    plan = workspace.plan if workspace else "free"

    if plan == "enterprise":
        limit = settings.enterprise_daily_whatsapp_limit
    elif plan == "pro":
        limit = settings.pro_daily_whatsapp_limit
    else:
        limit = 0

    # daily_sent_count is the current day's rolling counter (reset lazily); a
    # full per-day quota table can be added later if per-day history matters.
    used = account.daily_sent_count if account else 0
    return {
        "sent_count": used,
        "limit": limit,
        "remaining": max(0, limit - used),
    }