import logging
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_log import AuditLog
from app.db.models.platform_admin import PlatformAdmin

logger = logging.getLogger(__name__)


async def record_action(
    session: AsyncSession,
    *,
    actor: PlatformAdmin,
    action: str,
    target_type: str,
    target_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    before: Optional[dict[str, Any]] = None,
    after: Optional[dict[str, Any]] = None,
    ip_address: Optional[str] = None,
) -> None:
    """Records an admin mutation. Never raises — losing an audit row must never
    block or roll back the underlying admin action (the reverse would be worse).
    """
    try:
        entry = AuditLog(
            actor_email=actor.email,
            actor_clerk_user_id=actor.clerk_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            workspace_id=workspace_id,
            before=before,
            after=after,
            ip_address=ip_address,
        )
        session.add(entry)
        await session.commit()
    except Exception:
        logger.warning("Failed to write audit log entry for action=%s target=%s", action, target_id, exc_info=True)


async def list_entries(
    session: AsyncSession,
    *,
    actor_email: Optional[str] = None,
    action: Optional[str] = None,
    target_type: Optional[str] = None,
    workspace_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditLog]:
    query = select(AuditLog).order_by(AuditLog.created_at.desc())
    if actor_email:
        query = query.where(AuditLog.actor_email == actor_email)
    if action:
        query = query.where(AuditLog.action == action)
    if target_type:
        query = query.where(AuditLog.target_type == target_type)
    if workspace_id:
        query = query.where(AuditLog.workspace_id == workspace_id)
    query = query.offset(offset).limit(limit)
    result = await session.execute(query)
    return list(result.scalars().all())
