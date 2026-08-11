import asyncio
import json
from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.email_account import EmailAccount
from app.services import email_account_service


async def get_valid_access_token(account: EmailAccount) -> str:
    """Get a valid access token, refreshing if expired."""
    if account.token_expires_at:
        expiry = account.token_expires_at
        now = datetime.now(timezone.utc)
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        if expiry > now:
            return account.access_token

    if account.provider == "google":
        return await email_account_service.refresh_google_token(account)
    return account.access_token


async def get_gmail_messages(
    access_token: str,
    query: str = "in:inbox",
    page: int = 1,
    page_size: int = 10,
    max_total: int = 500,
) -> tuple[list[dict], bool]:
    """Fetch a page of Gmail messages (metadata only) with stable pagination.

    The list endpoint is walked internally (up to ``max_total`` ids), then only
    the current page's messages are detail-fetched so each page stays fast.
    Returns (items, has_more)."""
    ids: list[dict] = []
    next_token: Optional[str] = None

    async with httpx.AsyncClient(timeout=30.0) as client:
        while len(ids) < min(page * page_size, max_total):
            params = {"q": query, "maxResults": 200}
            if next_token:
                params["pageToken"] = next_token
            list_resp = await client.get(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages",
                headers={"Authorization": f"Bearer {access_token}"},
                params=params,
            )
            list_resp.raise_for_status()
            data = list_resp.json()
            batch = data.get("messages", [])
            if not batch:
                break
            ids.extend(batch)
            next_token = data.get("nextPageToken")
            if not next_token:
                break

        total = len(ids)
        start = (page - 1) * page_size
        page_ids = ids[start:start + page_size]
        has_more = start + page_size < total

        semaphore = asyncio.Semaphore(10)

        async def fetch_one(msg_ref: dict) -> dict:
            async with semaphore:
                msg_resp = await client.get(
                    f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_ref['id']}?format=metadata",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                msg_resp.raise_for_status()
                msg_data = msg_resp.json()

            headers_list = {h["name"].lower(): h["value"] for h in msg_data.get("payload", {}).get("headers", [])}
            return {
                "id": msg_data["id"],
                "thread_id": msg_data.get("threadId"),
                "subject": headers_list.get("subject", ""),
                "from": headers_list.get("from", ""),
                "to": headers_list.get("to", ""),
                "date": headers_list.get("date", ""),
                "snippet": msg_data.get("snippet", ""),
                "label_ids": msg_data.get("labelIds", []),
            }

        results = await asyncio.gather(*(fetch_one(r) for r in page_ids))
        return list(results), has_more


async def get_gmail_message_detail(access_token: str, message_id: str) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as client:
        msg_resp = await client.get(
            f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}?format=full",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        msg_resp.raise_for_status()
        msg_data = msg_resp.json()

        headers_list = {h["name"].lower(): h["value"] for h in msg_data.get("payload", {}).get("headers", [])}

        body = ""
        if "body" in msg_data.get("payload", {}):
            body = msg_data["payload"]["body"].get("data", "")
        elif "parts" in msg_data.get("payload", {}):
            for part in msg_data["payload"]["parts"]:
                if part["mimeType"] == "text/plain":
                    body = part.get("body", {}).get("data", "")
                    break

        import base64
        if body:
            body = base64.urlsafe_b64decode(body).decode("utf-8", errors="ignore")

        return {
            "id": msg_data["id"],
            "thread_id": msg_data.get("threadId"),
            "subject": headers_list.get("subject", ""),
            "from": headers_list.get("from", ""),
            "to": headers_list.get("to", ""),
            "date": headers_list.get("date", ""),
            "body": body,
            "snippet": msg_data.get("snippet", ""),
            "label_ids": msg_data.get("labelIds", []),
        }


async def send_gmail_message(
    access_token: str, to: str, subject: str, body: str, thread_id: Optional[str] = None
) -> dict:
    import base64
    from email.mime.text import MIMEText

    message = MIMEText(body, "html")
    message["to"] = to
    message["subject"] = subject
    if thread_id and "@" in thread_id:
        message["In-Reply-To"] = thread_id
        message["References"] = thread_id

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")

    payload: dict = {"raw": raw}
    if thread_id:
        payload["threadId"] = thread_id

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            headers={"Authorization": f"Bearer {access_token}"},
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()


async def sync_inbox(
    session: AsyncSession, account: EmailAccount, page: int = 1, page_size: int = 10, max_total: int = 500
) -> tuple[list[dict], bool]:
    access_token = await get_valid_access_token(account)
    if account.provider == "google":
        return await get_gmail_messages(access_token, "in:inbox", page=page, page_size=page_size, max_total=max_total)
    return [], False


async def sync_sent(
    session: AsyncSession, account: EmailAccount, page: int = 1, page_size: int = 10, max_total: int = 500
) -> tuple[list[dict], bool]:
    access_token = await get_valid_access_token(account)
    if account.provider == "google":
        return await get_gmail_messages(access_token, "in:sent", page=page, page_size=page_size, max_total=max_total)
    return [], False


async def sync_trash(
    session: AsyncSession, account: EmailAccount, page: int = 1, page_size: int = 10, max_total: int = 500
) -> tuple[list[dict], bool]:
    access_token = await get_valid_access_token(account)
    if account.provider == "google":
        return await get_gmail_messages(access_token, "in:trash", page=page, page_size=page_size, max_total=max_total)
    return [], False


async def sync_spam(
    session: AsyncSession, account: EmailAccount, page: int = 1, page_size: int = 10, max_total: int = 500
) -> tuple[list[dict], bool]:
    access_token = await get_valid_access_token(account)
    if account.provider == "google":
        return await get_gmail_messages(access_token, "in:spam", page=page, page_size=page_size, max_total=max_total)
    return [], False


async def get_email_detail(session: AsyncSession, account: EmailAccount, message_id: str) -> dict:
    access_token = await get_valid_access_token(account)
    if account.provider == "google":
        return await get_gmail_message_detail(access_token, message_id)
    return {}


async def send_email_from_account(
    session: AsyncSession, account: EmailAccount, to: str, subject: str, body: str, thread_id: Optional[str] = None
) -> dict:
    access_token = await get_valid_access_token(account)
    if account.provider == "google":
        return await send_gmail_message(access_token, to, subject, body, thread_id=thread_id)
    return {"status": "unsupported"}
