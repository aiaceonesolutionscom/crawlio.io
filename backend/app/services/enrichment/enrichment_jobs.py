"""Redis-backed store for in-flight lead-enrichment jobs.

The discovery API returns candidate leads immediately and a Celery worker
enriches them in the background; the frontend polls a status endpoint that reads
this store, so the UI shows live "enriching -> done" progress per lead. Everything
degrades gracefully: if Redis is unreachable, job creation fails cleanly and the
API falls back to inline enrichment.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

JOB_PREFIX = "enrichment:"
JOB_TTL_SECONDS = 60 * 60  # search results are transient; drop them after an hour


def _client() -> aioredis.Redis:
    return aioredis.from_url(
        settings.redis_url,
        socket_connect_timeout=2,
        socket_timeout=3,
        decode_responses=True,
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def create_enrichment_job(search_id: str, items: list[dict], meta: dict) -> bool:
    """Store a new job. Returns False if Redis is unavailable (caller falls back
    to inline enrichment rather than letting the leads rot at partial data)."""
    payload = {
        "search_id": search_id,
        "status": "in_progress",
        "meta": meta,
        "items": items,
        "created_at": _now(),
    }
    try:
        client = _client()
        await client.set(f"{JOB_PREFIX}{search_id}", json.dumps(payload, default=str), ex=JOB_TTL_SECONDS)
        await client.aclose()
        return True
    except Exception as exc:
        logger.warning("Redis unavailable, enrichment job %s not stored: %s", search_id, exc)
        return False


async def get_enrichment_job(search_id: str) -> Optional[dict]:
    try:
        client = _client()
        raw = await client.get(f"{JOB_PREFIX}{search_id}")
        await client.aclose()
        if not raw:
            return None
        return json.loads(raw)
    except Exception as exc:
        logger.warning("Could not read enrichment job %s: %s", search_id, exc)
        return None


async def _save_job(search_id: str, job: dict) -> None:
    try:
        client = _client()
        await client.set(f"{JOB_PREFIX}{search_id}", json.dumps(job, default=str), ex=JOB_TTL_SECONDS)
        await client.aclose()
    except Exception as exc:
        logger.warning("Could not persist enrichment job %s: %s", search_id, exc)


async def update_item(search_id: str, index: int, patch: dict, *, lock=None) -> None:
    """Merge `patch` into one item of the job and recompute the job status. A
    process-local lock serializes concurrent updates from the same batch."""
    if lock is not None:
        await lock.acquire()
    try:
        job = await get_enrichment_job(search_id)
        if not job:
            return
        items = job.get("items", [])
        if index >= len(items):
            return
        items[index] = {**items[index], **patch}
        terminal = all(
            it.get("enrichment_status") in ("done", "failed") for it in items
        )
        job["status"] = "done" if terminal else "in_progress"
        await _save_job(search_id, job)
    finally:
        if lock is not None:
            lock.release()
