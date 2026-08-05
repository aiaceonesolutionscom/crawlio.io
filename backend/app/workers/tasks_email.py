import asyncio
import logging

from app.core.config import settings
from app.services import email_service
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="send_welcome_email")
def send_welcome_email_task(to_email: str, name: str, workspace_name: str) -> None:
    asyncio.run(_send_welcome_email_async(to_email, name, workspace_name))


async def _send_welcome_email_async(to_email: str, name: str, workspace_name: str) -> None:
    if not settings.brevo_api_key:
        logger.info("BREVO_API_KEY not configured; skipping welcome email to %s", to_email)
        return
    try:
        html = email_service.welcome_email_html(name, workspace_name)
        await email_service.send_email(to_email, "Welcome to Crawlio", html)
    except Exception:
        logger.exception("Failed to send welcome email to %s", to_email)


@celery_app.task(name="send_invite_email")
def send_invite_email_task(to_email: str, workspace_name: str, role: str) -> None:
    asyncio.run(_send_invite_email_async(to_email, workspace_name, role))


async def _send_invite_email_async(to_email: str, workspace_name: str, role: str) -> None:
    if not settings.brevo_api_key:
        logger.info("BREVO_API_KEY not configured; skipping invite email to %s", to_email)
        return
    try:
        html = email_service.invite_email_html(workspace_name, role)
        await email_service.send_email(to_email, f"You're invited to {workspace_name} on Crawlio", html)
    except Exception:
        logger.exception("Failed to send invite email to %s", to_email)
