from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin_deps import require_permission
from app.core.permissions import PERMISSION_AUDIT_READ
from app.db.models.platform_admin import PlatformAdmin
from app.db.session import get_session
from app.schemas.admin import AuditLogRead
from app.services.admin import audit_service

router = APIRouter(prefix="/audit-log", tags=["admin:audit-log"])


@router.get("", response_model=list[AuditLogRead])
async def list_audit_log(
    admin: Annotated[PlatformAdmin, Depends(require_permission(PERMISSION_AUDIT_READ))],
    session: Annotated[AsyncSession, Depends(get_session)],
    actor_email: Optional[str] = Query(default=None),
    action: Optional[str] = Query(default=None),
    target_type: Optional[str] = Query(default=None),
    workspace_id: Optional[str] = Query(default=None),
    limit: int = Query(default=100, le=200),
    offset: int = Query(default=0, ge=0),
):
    return await audit_service.list_entries(
        session,
        actor_email=actor_email,
        action=action,
        target_type=target_type,
        workspace_id=workspace_id,
        limit=limit,
        offset=offset,
    )
