"""Redis pub/sub + persisted provenance for the AI agent's real-time activity.
Emit is order-agnostic: if Redis is down the event is still persisted to the
DB so a later WebSocket replay can deliver it (no fake/spurious events)."""

import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.agent import AIActivity


def _channel(workspace_id: str) -> str:
    return f"agent:{workspace_id}"


async def publish_activity(
    session: AsyncSession,
    workspace_id: str,
    stage: str,
    status: str = "done",
    conversation_id: Optional[str] = None,
    detail: Optional[str] = None,
) -> None:
    session.add(
        AIActivity(
            workspace_id=workspace_id,
            conversation_id=conversation_id,
            stage=stage,
            status=status,
            detail=detail,
        )
    )
    try:
        import redis.asyncio as redis_async

        cache = redis_async.from_url(settings.redis_url, decode_responses=True)
        await cache.publish(
            _channel(workspace_id),
            json.dumps({
                "type": "ai_activity",
                "workspace_id": workspace_id,
                "conversation_id": conversation_id,
                "stage": stage,
                "status": status,
                "detail": detail,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }),
        )
        await cache.aclose()
    except Exception:
        # Persistence above is the source of truth; pub/sub is best-effort.
        pass


async def list_recent_activity(
    session: AsyncSession, workspace_id: str, limit: int = 50
) -> list[AIActivity]:
    from sqlalchemy import select

    result = await session.execute(
        select(AIActivity)
        .where(AIActivity.workspace_id == workspace_id)
        .order_by(AIActivity.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())