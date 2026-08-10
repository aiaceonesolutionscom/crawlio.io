from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin_deps import require_super_admin
from app.db.models.platform_admin import PlatformAdmin
from app.db.session import get_session
from app.schemas.admin import PlatformAdminCreate, PlatformAdminRead
from app.services import audit_service, platform_admin_service

router = APIRouter(prefix="/platform-admins", tags=["admin:platform-admins"])


@router.get("", response_model=list[PlatformAdminRead])
async def list_platform_admins(
    admin: Annotated[PlatformAdmin, Depends(require_super_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    return await platform_admin_service.list_admins(session)


@router.post("", response_model=PlatformAdminRead, status_code=201)
async def add_platform_admin(
    payload: PlatformAdminCreate,
    admin: Annotated[PlatformAdmin, Depends(require_super_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
    request: Request,
):
    created = await platform_admin_service.add_admin(session, payload.email, added_by=admin.email)
    await audit_service.record_action(
        session,
        actor=admin,
        action="platform_admin.add",
        target_type="platform_admin",
        target_id=created.id,
        after={"email": created.email},
        ip_address=request.client.host if request.client else None,
    )
    return created


@router.delete("/{admin_id}", response_model=PlatformAdminRead)
async def revoke_platform_admin(
    admin_id: str,
    admin: Annotated[PlatformAdmin, Depends(require_super_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
    request: Request,
):
    revoked = await platform_admin_service.revoke_admin(session, admin_id)
    await audit_service.record_action(
        session,
        actor=admin,
        action="platform_admin.revoke",
        target_type="platform_admin",
        target_id=revoked.id,
        before={"email": revoked.email, "is_active": True},
        after={"email": revoked.email, "is_active": False},
        ip_address=request.client.host if request.client else None,
    )
    return revoked
