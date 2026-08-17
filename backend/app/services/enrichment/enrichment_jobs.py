"""Store for in-flight discovery/enrichment jobs.

The discovery API returns a search_id immediately and crawls in the background;
the frontend polls a status endpoint that reads this store, so the UI shows live
"crawling -> enriching -> done" progress per lead. Redis is the primary store
(survives restarts, shared across workers). When Redis is unavailable the store
degrades to a process-local dict so the feature still works — jobs just don't
survive a backend restart, which is acceptable for local/offline runs.
"""
import json
import logging
import time
from datetime import datetime, timezone
from typing import Optional

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

JOB_PREFIX = "enrichment:"
JOB_TTL_SECONDS = 60 * 60  # search results are transient; drop them after an hour

# Process-local fallback store used when Redis is unreachable.
_MEM_JOBS: dict[str, dict] = {}

# Fast-fail flag: once Redis is confirmed unreachable we stop attempting a 2s
# connect + 3s socket timeout on every get/save (each poll during a background
# search hit that timeout). We retry Redis occasionally so it reconnects as
# soon as the server actually comes back.
_REDIS_OK: Optional[bool] = None
_REDIS_RETRY_AFTER_SECONDS = 15.0
_REDIS_LAST_ATTEMPT = 0.0


def _redis_available() -> bool:
    """Whether to attempt Redis this call. True until proven unavailable; after
    a failure, False for a short cooldown, then re-probed."""
    global _REDIS_OK, _REDIS_LAST_ATTEMPT
    if _REDIS_OK is not False:
        return True
    if time.monotonic() - _REDIS_LAST_ATTEMPT >= _REDIS_RETRY_AFTER_SECONDS:
        return True  # allow a re-probe
    return False


def _mark_redis_down() -> None:
    global _REDIS_OK, _REDIS_LAST_ATTEMPT
    _REDIS_OK = False
    _REDIS_LAST_ATTEMPT = time.monotonic()


def _mark_redis_up() -> None:
    global _REDIS_OK
    _REDIS_OK = True


def _client() -> Optional[aioredis.Redis]:
    if not _redis_available():
        return None
    return aioredis.from_url(
        settings.redis_url,
        socket_connect_timeout=2,
        socket_timeout=3,
        decode_responses=True,
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_job(search_id: str, items: list[dict], meta: dict) -> dict:
    return {
        "search_id": search_id,
        "status": "in_progress",
        "meta": meta,
        "items": items,
        "created_at": _now(),
    }


async def create_enrichment_job(search_id: str, items: list[dict], meta: dict) -> bool:
    """Store a new job. Falls back to the process-local dict when Redis is
    unreachable, so callers can always proceed with the background flow."""
    payload = _make_job(search_id, items, meta)
    client = _client()
    if client is not None:
        try:
            await client.set(f"{JOB_PREFIX}{search_id}", json.dumps(payload, default=str), ex=JOB_TTL_SECONDS)
            _mark_redis_up()
        except Exception as exc:
            logger.warning("Redis unavailable, enrichment job %s kept in memory: %s", search_id, exc)
            _mark_redis_down()
        finally:
            await client.aclose()
    _MEM_JOBS[search_id] = payload
    return True


async def get_enrichment_job(search_id: str) -> Optional[dict]:
    client = _client()
    if client is not None:
        try:
            raw = await client.get(f"{JOB_PREFIX}{search_id}")
            _mark_redis_up()
            await client.aclose()
            if raw:
                return json.loads(raw)
        except Exception as exc:
            logger.warning("Could not read enrichment job %s from Redis: %s", search_id, exc)
            _mark_redis_down()
            await client.aclose()
    return _MEM_JOBS.get(search_id)


async def save_job(search_id: str, job: dict) -> None:
    """Persist a job snapshot (Redis best-effort, then the in-memory fallback)."""
    _MEM_JOBS[search_id] = job
    client = _client()
    if client is not None:
        try:
            await client.set(f"{JOB_PREFIX}{search_id}", json.dumps(job, default=str), ex=JOB_TTL_SECONDS)
            _mark_redis_up()
        except Exception as exc:
            logger.warning("Could not persist enrichment job %s to Redis: %s", search_id, exc)
            _mark_redis_down()
        finally:
            await client.aclose()


async def fail_job(search_id: str, detail: str) -> None:
    """Mark a job as failed so the polling UI can surface the error."""
    job = await get_enrichment_job(search_id) or _make_job(search_id, [], {})
    job["status"] = "failed"
    job["error"] = detail
    await save_job(search_id, job)


async def _save_job(search_id: str, job: dict) -> None:
    await save_job(search_id, job)


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
