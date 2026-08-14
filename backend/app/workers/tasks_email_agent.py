import asyncio
import logging

from celery.exceptions import MaxRetriesExceededError

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="reset_daily_email_quota", bind=True)
def reset_daily_email_quota_task(self) -> None:
    try:
        asyncio.run(_reset_daily_quota_async())
    except Exception as exc:
        logger.exception("Failed to reset daily email quota")


async def _reset_daily_quota_async() -> None:
    from datetime import datetime, timezone
    from sqlalchemy import select, delete
    from app.db.session import async_session_maker
    from app.db.models.email_account import DailyEmailQuota

    yesterday = (datetime.now(timezone.utc)).strftime("%Y-%m-%d")
    async with async_session_maker() as session:
        await session.execute(
            delete(DailyEmailQuota).where(DailyEmailQuota.date < yesterday)
        )
        await session.commit()
        logger.info("Reset daily email quota for date: %s", yesterday)


@celery_app.task(name="sync_email_account", bind=True, max_retries=3)
def sync_email_account_task(self, account_id: str) -> None:
    try:
        asyncio.run(_sync_email_account_async(account_id))
    except Exception as exc:
        logger.warning("Sync attempt %s failed for account %s", self.request.retries + 1, account_id)
        try:
            raise self.retry(countdown=60)
        except MaxRetriesExceededError:
            logger.exception("Email sync exhausted retries for account %s", account_id)


async def _sync_email_account_async(account_id: str) -> None:
    from datetime import datetime, timezone
    from sqlalchemy import select
    from app.db.session import async_session_maker
    from app.db.models.email_account import EmailAccount
    from app.services.automation import email_sync_service

    async with async_session_maker() as session:
        result = await session.execute(
            select(EmailAccount).where(EmailAccount.id == account_id)
        )
        account = result.scalar_one_or_none()
        if not account:
            return

        try:
            inbox = await email_sync_service.sync_inbox(session, account)
            sent = await email_sync_service.sync_sent(session, account)
            logger.info(
                "Synced email account %s: %d inbox, %d sent",
                account.email_address, len(inbox), len(sent)
            )
        except Exception as exc:
            logger.warning("Failed to sync emails for %s: %s", account.email_address, exc)

        account.last_synced_at = datetime.now(timezone.utc)
        await session.commit()
        logger.info("Updated sync timestamp for: %s", account.email_address)


@celery_app.task(name="send_approved_email", bind=True, max_retries=3)
def send_approved_email_task(self, draft_id: str) -> None:
    try:
        asyncio.run(_send_approved_email_async(draft_id))
    except Exception as exc:
        logger.warning("Send attempt %s failed for draft %s", self.request.retries + 1, draft_id)
        try:
            raise self.retry(countdown=30)
        except MaxRetriesExceededError:
            logger.exception("Email send exhausted retries for draft %s", draft_id)


async def _send_approved_email_async(draft_id: str) -> None:
    from sqlalchemy import select
    from app.db.session import async_session_maker
    from app.db.models.email_account import EmailDraft
    from app.services.automation.email_compose_service import send_draft


    async with async_session_maker() as session:
        result = await session.execute(
            select(EmailDraft).where(EmailDraft.id == draft_id)
        )
        draft = result.scalar_one_or_none()
        if not draft or draft.status != "approved":
            return

        await send_draft(session, draft_id)
        logger.info("Sent approved email for draft: %s", draft_id)
