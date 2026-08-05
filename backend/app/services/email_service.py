from typing import Any, Optional

import httpx

from app.core.config import settings

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


async def send_email(to: str, subject: str, html: str) -> dict[str, Any]:
    if not settings.brevo_api_key:
        raise RuntimeError("BREVO_API_KEY is not configured")

    payload = {
        "sender": {"email": settings.brevo_sender_email, "name": settings.brevo_sender_name},
        "to": [{"email": to}],
        "subject": subject,
        "htmlContent": html
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            BREVO_API_URL,
            headers={"api-key": settings.brevo_api_key, "Content-Type": "application/json", "Accept": "application/json"},
            json=payload
        )
        resp.raise_for_status()
        return resp.json()


def welcome_email_html(name: str, workspace_name: str) -> str:
    return (
        f"<div style=\"font-family:sans-serif\">"
        f"<h2>Welcome to Crawlio, {name}.</h2>"
        f"<p>Your workspace <strong>{workspace_name}</strong> is live on the Free plan.</p>"
        f"<p>Start by adding your first lead from the dashboard.</p>"
        f"</div>"
    )


def invite_email_html(workspace_name: str, role: str) -> str:
    return (
        f"<div style=\"font-family:sans-serif\">"
        f"<h2>You're invited to {workspace_name} on Crawlio.</h2>"
        f"<p>You've been invited as a <strong>{role}</strong>.</p>"
        f"<p>Sign up at Crawlio with this email address to join the workspace.</p>"
        f"</div>"
    )


def sequence_step_html(body: str) -> str:
    paragraphs = "".join(f"<p>{line}</p>" for line in body.splitlines() if line.strip())
    return f"<div style=\"font-family:sans-serif\">{paragraphs}</div>"
