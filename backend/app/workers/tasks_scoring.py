import asyncio
import logging

from sqlalchemy import select

from app.db.models.lead import Lead
from app.db.session import async_session_maker
from app.services import lead_service, scoring_service
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="score_lead")
def score_lead_task(lead_id: str) -> None:
    asyncio.run(_score_lead_async(lead_id))


async def _score_lead_async(lead_id: str) -> None:
    async with async_session_maker() as session:
        result = await session.execute(select(Lead).where(Lead.id == lead_id))
        lead = result.scalar_one_or_none()
        if lead is None:
            return

        try:
            outcome = await scoring_service.score_lead(lead.name, lead.company, lead.email, lead.source)
        except Exception:
            logger.exception("Mistral scoring failed for lead %s; leaving it unscored", lead_id)
            return

        await lead_service.apply_score(session, lead_id, outcome["score"], outcome["status"])
