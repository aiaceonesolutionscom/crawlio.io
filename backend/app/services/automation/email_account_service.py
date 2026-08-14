import json
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.integration_runtime import api_key
from app.db.models.email_account import DailyEmailQuota, EmailAccount


async def get_google_auth_url(state: str) -> str:
    params = {
        "client_id": api_key("google_client_id"),
        "redirect_uri": api_key("google_redirect_uri"),
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/gmail.modify https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/userinfo.profile",
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"https://accounts.google.com/o/oauth2/v2/auth?{query}"


async def exchange_google_code(code: str) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": api_key("google_client_id"),
                "client_secret": api_key("google_client_secret"),
                "redirect_uri": api_key("google_redirect_uri"),
                "grant_type": "authorization_code",
            },
        )
        resp.raise_for_status()
        return resp.json()


async def refresh_google_token(account: EmailAccount) -> str:
    if not account.refresh_token:
        raise RuntimeError("No refresh token available")
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "refresh_token": account.refresh_token,
                "client_id": api_key("google_client_id"),
                "client_secret": api_key("google_client_secret"),
                "grant_type": "refresh_token",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["access_token"]


async def get_google_user_info(access_token: str) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        return resp.json()


async def connect_gmail_account(
    session: AsyncSession, workspace_id: str, user_id: str, code: str
) -> EmailAccount:
    token_data = await exchange_google_code(code)
    access_token = token_data["access_token"]
    refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in", 3600)

    user_info = await get_google_user_info(access_token)
    email = user_info.get("email", "")
    name = user_info.get("name", "")

    expires_at = datetime.now(timezone.utc).replace(
        second=0, microsecond=0
    ) + timedelta(seconds=expires_in)

    account = EmailAccount(
        workspace_id=workspace_id,
        user_id=user_id,
        email_address=email,
        display_name=name,
        provider="google",
        access_token=access_token,
        refresh_token=refresh_token,
        token_expires_at=expires_at,
    )
    session.add(account)
    await session.commit()
    await session.refresh(account)
    return account


async def list_email_accounts(session: AsyncSession, workspace_id: str) -> list[EmailAccount]:
    result = await session.execute(
        select(EmailAccount).where(EmailAccount.workspace_id == workspace_id)
    )
    return list(result.scalars().all())


async def get_email_account(session: AsyncSession, account_id: str) -> Optional[EmailAccount]:
    result = await session.execute(
        select(EmailAccount).where(EmailAccount.id == account_id)
    )
    return result.scalar_one_or_none()


async def disconnect_email_account(session: AsyncSession, account_id: str) -> None:
    account = await get_email_account(session, account_id)
    if account:
        await session.delete(account)
        await session.commit()


async def check_daily_quota(
    session: AsyncSession, workspace_id: str, email_account_id: str
) -> dict:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    result = await session.execute(
        select(DailyEmailQuota).where(
            DailyEmailQuota.workspace_id == workspace_id,
            DailyEmailQuota.email_account_id == email_account_id,
            DailyEmailQuota.date == today,
        )
    )
    quota = result.scalar_one_or_none()
    if not quota:
        quota = DailyEmailQuota(
            workspace_id=workspace_id,
            email_account_id=email_account_id,
            date=today,
        )
        session.add(quota)
        await session.commit()
        await session.refresh(quota)

    from app.db.models.workspace import Workspace

    ws_result = await session.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = ws_result.scalar_one_or_none()
    plan = workspace.plan if workspace else "free"

    if plan == "enterprise":
        limit = settings.enterprise_daily_email_limit
    elif plan == "pro":
        limit = settings.pro_daily_email_limit
    else:
        limit = 0

    return {
        "composed_count": quota.composed_count,
        "ai_generated_count": quota.ai_generated_count,
        "total_sent": quota.total_sent,
        "limit": limit,
        "remaining": max(0, limit - quota.total_sent),
    }


async def increment_sent_count(
    session: AsyncSession, workspace_id: str, email_account_id: str, kind: str
) -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    result = await session.execute(
        select(DailyEmailQuota).where(
            DailyEmailQuota.workspace_id == workspace_id,
            DailyEmailQuota.email_account_id == email_account_id,
            DailyEmailQuota.date == today,
        )
    )
    quota = result.scalar_one_or_none()
    if not quota:
        quota = DailyEmailQuota(
            workspace_id=workspace_id,
            email_account_id=email_account_id,
            date=today,
        )
        session.add(quota)

    quota.total_sent += 1
    if kind == "composed":
        quota.composed_count += 1
    elif kind == "ai_generated":
        quota.ai_generated_count += 1

    await session.commit()
