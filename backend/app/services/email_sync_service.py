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
    elif account.provider == "microsoft":
        return await email_account_service.refresh_microsoft_token(account)
    return account.access_token


async def get_gmail_messages(access_token: str, query: str = "in:inbox", max_results: int = 50) -> list[dict]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        list_resp = await client.get(
            f"https://gmail.googleapis.com/gmail/v1/users/me/messages?q={query}&maxResults={max_results}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        list_resp.raise_for_status()
        messages = list_resp.json().get("messages", [])

        result = []
        for msg_ref in messages[:max_results]:
            msg_resp = await client.get(
                f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_ref['id']}?format=metadata",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            msg_resp.raise_for_status()
            msg_data = msg_resp.json()

            headers_list = {h["name"].lower(): h["value"] for h in msg_data.get("payload", {}).get("headers", [])}
            result.append({
                "id": msg_data["id"],
                "thread_id": msg_data.get("threadId"),
                "subject": headers_list.get("subject", ""),
                "from": headers_list.get("from", ""),
                "to": headers_list.get("to", ""),
                "date": headers_list.get("date", ""),
                "snippet": msg_data.get("snippet", ""),
                "label_ids": msg_data.get("labelIds", []),
            })

        return result


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


async def send_gmail_message(access_token: str, to: str, subject: str, body: str) -> dict:
    import base64
    from email.mime.text import MIMEText

    message = MIMEText(body, "html")
    message["to"] = to
    message["subject"] = subject

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"raw": raw},
        )
        resp.raise_for_status()
        return resp.json()


async def get_outlook_messages(access_token: str, folder: str = "inbox", top: int = 50) -> list[dict]:
    folder_path = (
        "inbox"
        if folder == "inbox"
        else "sentItems"
        if folder == "sent"
        else "junkemail"
        if folder == "spam"
        else "deletedItems"
    )
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"https://graph.microsoft.com/v1.0/me/mailFolders/{folder_path}/messages?$top={top}&$orderby=receivedDateTime desc",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        data = resp.json()

        result = []
        for msg in data.get("value", []):
            result.append({
                "id": msg["id"],
                "thread_id": msg.get("conversationId"),
                "subject": msg.get("subject", ""),
                "from": msg.get("from", {}).get("emailAddress", {}).get("address", ""),
                "to": msg.get("toRecipients", [{}])[0].get("emailAddress", {}).get("address", "") if msg.get("toRecipients") else "",
                "date": msg.get("receivedDateTime", ""),
                "body_preview": msg.get("bodyPreview", ""),
                "is_read": msg.get("isRead", True),
            })

        return result


async def get_outlook_message_detail(access_token: str, message_id: str) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"https://graph.microsoft.com/v1.0/me/messages/{message_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        msg = resp.json()

        return {
            "id": msg["id"],
            "thread_id": msg.get("conversationId"),
            "subject": msg.get("subject", ""),
            "from": msg.get("from", {}).get("emailAddress", {}).get("address", ""),
            "to": msg.get("toRecipients", [{}])[0].get("emailAddress", {}).get("address", "") if msg.get("toRecipients") else "",
            "date": msg.get("receivedDateTime", ""),
            "body": msg.get("body", {}).get("content", ""),
            "body_preview": msg.get("bodyPreview", ""),
            "is_read": msg.get("isRead", True),
        }


async def send_outlook_message(access_token: str, to: str, subject: str, body: str) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            "https://graph.microsoft.com/v1.0/me/sendMail",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json={
                "message": {
                    "subject": subject,
                    "body": {"contentType": "HTML", "content": body},
                    "toRecipients": [{"emailAddress": {"address": to}}],
                },
                "saveToSentItems": "true",
            },
        )
        resp.raise_for_status()
        return {"status": "sent"}


async def sync_inbox(session: AsyncSession, account: EmailAccount) -> list[dict]:
    access_token = await get_valid_access_token(account)
    if account.provider == "google":
        return await get_gmail_messages(access_token, "in:inbox")
    elif account.provider == "microsoft":
        return await get_outlook_messages(access_token, "inbox")
    return []


async def sync_sent(session: AsyncSession, account: EmailAccount) -> list[dict]:
    access_token = await get_valid_access_token(account)
    if account.provider == "google":
        return await get_gmail_messages(access_token, "in:sent")
    elif account.provider == "microsoft":
        return await get_outlook_messages(access_token, "sent")
    return []


async def sync_trash(session: AsyncSession, account: EmailAccount) -> list[dict]:
    access_token = await get_valid_access_token(account)
    if account.provider == "google":
        return await get_gmail_messages(access_token, "in:trash")
    elif account.provider == "microsoft":
        return await get_outlook_messages(access_token, "trash")
    return []


async def sync_spam(session: AsyncSession, account: EmailAccount) -> list[dict]:
    access_token = await get_valid_access_token(account)
    if account.provider == "google":
        return await get_gmail_messages(access_token, "in:spam")
    elif account.provider == "microsoft":
        return await get_outlook_messages(access_token, "spam")
    return []


async def get_email_detail(session: AsyncSession, account: EmailAccount, message_id: str) -> dict:
    access_token = await get_valid_access_token(account)
    if account.provider == "google":
        return await get_gmail_message_detail(access_token, message_id)
    elif account.provider == "microsoft":
        return await get_outlook_message_detail(access_token, message_id)
    return {}


async def send_email_from_account(
    session: AsyncSession, account: EmailAccount, to: str, subject: str, body: str
) -> dict:
    access_token = await get_valid_access_token(account)
    if account.provider == "google":
        return await send_gmail_message(access_token, to, subject, body)
    elif account.provider == "microsoft":
        return await send_outlook_message(access_token, to, subject, body)
    return {"status": "unsupported"}
