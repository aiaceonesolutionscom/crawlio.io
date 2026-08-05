import asyncio
import logging

from celery.exceptions import MaxRetriesExceededError
from sqlalchemy import select

from app.db.models.lead import Lead
from app.db.session import async_session_maker
from app.services import lead_service, scoring_service
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

MAX_SCORING_RETRIES = 3
RETRY_DELAY_SECONDS = 60


@celery_app.task(name="score_lead", bind=True, max_retries=MAX_SCORING_RETRIES)
def score_lead_task(self, lead_id: str) -> None:
    try:
        asyncio.run(_score_lead_async(lead_id))
    except Exception as exc:
        logger.warning("Scoring attempt %s failed for lead %s", self.request.retries + 1, lead_id)
        try:
            # Deliberately omit exc= here: passing it makes Celery re-raise the
            # original exception once retries are exhausted instead of raising
            # MaxRetriesExceededError, which would skip the except clause below
            # and leave the lead silently stuck at score=None forever.
            raise self.retry(countdown=RETRY_DELAY_SECONDS)
        except MaxRetriesExceededError:
            logger.exception("Mistral scoring exhausted retries for lead %s", lead_id)
            asyncio.run(_mark_scoring_failed(lead_id))


async def _score_lead_async(lead_id: str) -> None:
    async with async_session_maker() as session:
        result = await session.execute(select(Lead).where(Lead.id == lead_id))
        lead = result.scalar_one_or_none()
        if lead is None:
            return

        outcome = await scoring_service.score_lead(lead.name, lead.company, lead.email, lead.source)
        await lead_service.apply_score(session, lead_id, outcome["score"], outcome["status"])


async def _mark_scoring_failed(lead_id: str) -> None:
    async with async_session_maker() as session:
        await lead_service.mark_scoring_failed(session, lead_id)
