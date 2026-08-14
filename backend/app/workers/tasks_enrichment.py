import asyncio
import logging

from celery.exceptions import MaxRetriesExceededError
from sqlalchemy import select

from app.db.models.lead import Lead
from app.db.session import async_session_maker
from app.services.discovery import discovery_cache_service
from app.services.enrichment import enrichment_jobs, enrichment_pipeline
from app.services.lead import lead_service
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# How many discovered leads are enriched concurrently in one batch. Scraping is
# the heavy part (Playwright already caps at 6 pages anyway), so this just keeps
# memory/concurrent-scrape bursts bounded.
BATCH_CONCURRENCY = 6


@celery_app.task(name="enrich_discovered_batch", bind=True, max_retries=1)
def enrich_discovered_batch(
    self,
    search_id: str,
    city: str,
    country: str,
    country_code: str = "",
    use_browser: bool = True,
    use_ai: bool = True,
    use_google_maps: bool = False,
) -> None:
    try:
        asyncio.run(
            _enrich_batch_async(search_id, city, country, country_code, use_browser, use_ai, use_google_maps)
        )
    except Exception as exc:
        logger.exception("Batch enrichment failed for job %s", search_id)
        raise self.retry(countdown=30)


async def _enrich_batch_async(
    search_id: str,
    city: str,
    country: str,
    country_code: str,
    use_browser: bool,
    use_ai: bool,
    use_google_maps: bool = False,
) -> None:
    job = await enrichment_jobs.get_enrichment_job(search_id)
    if not job:
        logger.warning("Enrichment job %s not found; nothing to do", search_id)
        return

    items = job.get("items", [])
    lock = asyncio.Lock()
    semaphore = asyncio.Semaphore(BATCH_CONCURRENCY)

    async def _work(index: int, item: dict) -> None:
        async with semaphore:
            try:
                enriched = await enrichment_pipeline.enrich_item(
                    item,
                    city=city,
                    country=country,
                    country_code=country_code or None,
                    use_browser=use_browser,
                    use_ai=use_ai,
                    use_google_maps=use_google_maps,
                )
                enriched["enrichment_status"] = enriched.get("enrichment_status") or "done"
                await enrichment_jobs.update_item(search_id, index, enriched, lock=lock)
            except Exception as exc:
                logger.warning("Enrichment failed for item %s: %s", item.get("name"), exc)
                await enrichment_jobs.update_item(
                    search_id,
                    index,
                    {"enrichment_status": "failed", "enrichment_error": str(exc)[:200]},
                    lock=lock,
                )

    await asyncio.gather(*(_work(i, item) for i, item in enumerate(items)))

    # Refresh the discovery cache now that these leads have their real
    # website-scraped email/social data — cache readers before this point only
    # saw the faster, phone/address-only snapshot written at request time.
    final_job = await enrichment_jobs.get_enrichment_job(search_id)
    niche = (final_job or {}).get("meta", {}).get("niche")
    if final_job and niche:
        async with async_session_maker() as session:
            await discovery_cache_service.upsert_cache(
                session, niche, city, country_code or "",
                niche_display=niche, city_display=city, country_display=country,
                items=final_job.get("items", []),
            )


@celery_app.task(name="enrich_lead", bind=True, max_retries=2)
def enrich_lead(
    self, lead_id: str, city: str = "", country: str = "", country_code: str = ""
) -> None:
    """Re-run the full enrichment pipeline on a single already-saved lead
    (used by the "Filter your leads" AI filter). Writes enriched data back to
    the lead via gap-fill + metadata."""
    try:
        asyncio.run(_enrich_lead_async(lead_id, city, country, country_code))
    except Exception as exc:
        logger.warning("Enrichment attempt %s failed for lead %s", self.request.retries + 1, lead_id)
        try:
            raise self.retry(countdown=30)
        except MaxRetriesExceededError:
            logger.exception("Enrichment exhausted retries for lead %s", lead_id)
            asyncio.run(_mark_enrichment_failed(lead_id))


async def _enrich_lead_async(lead_id: str, city: str, country: str, country_code: str) -> None:
    async with async_session_maker() as session:
        result = await session.execute(select(Lead).where(Lead.id == lead_id))
        lead = result.scalar_one_or_none()
        if lead is None:
            return

        metadata = dict(lead.lead_metadata or {})
        item = {
            "name": lead.name,
            "phone": lead.phone,
            "email": lead.email,
            "website": lead.website,
            "address": lead.address or metadata.get("address"),
            "social_links": metadata.get("social_links") or {},
        }
        enriched = await enrichment_pipeline.enrich_item(
            item,
            city=city,
            country=country,
            country_code=country_code or None,
            use_browser=True,
            use_ai=True,
            use_google_maps=True,
        )

        lead_service.apply_enrichment_to_lead(lead, enriched)

        metadata = dict(lead.lead_metadata or {})
        if enriched.get("address"):
            lead.address = lead.address or enriched["address"]
        for key in ("description", "hours", "completeness", "enrichment_source", "last_enriched_at"):
            if enriched.get(key):
                metadata[key] = enriched[key]
        metadata["enrichment_status"] = enriched.get("enrichment_status") or "done"
        lead.lead_metadata = metadata or None
        await session.commit()


async def _mark_enrichment_failed(lead_id: str) -> None:
    async with async_session_maker() as session:
        result = await session.execute(select(Lead).where(Lead.id == lead_id))
        lead = result.scalar_one_or_none()
        if lead is None:
            return
        metadata = dict(lead.lead_metadata or {})
        metadata["enrichment_status"] = "failed"
        lead.lead_metadata = metadata or None
        await session.commit()
