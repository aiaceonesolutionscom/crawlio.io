from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin_deps import get_current_admin, require_permission, require_role
from app.core.permissions import (
    PERMISSION_ADMINS_READ,
    PERMISSION_ADMINS_WRITE,
    ROLE_SUPER_ADMIN,
    is_valid_permission,
)
from app.db.models.platform_admin import PlatformAdmin
from app.db.session import get_session
from app.schemas.admin import (
    AdminPermissionCreate,
    AdminPermissionRead,
    PlatformAdminCreate,
    PlatformAdminRead,
    PlatformAdminRoleUpdate,
)
from app.services.admin import audit_service, platform_admin_service

router = APIRouter(prefix="/platform-admins", tags=["admin:platform-admins"])


@router.get("", response_model=list[PlatformAdminRead])
async def list_platform_admins(
    admin: Annotated[PlatformAdmin, Depends(require_permission(PERMISSION_ADMINS_READ))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    return await platform_admin_service.list_admins(session)


@router.post("", response_model=PlatformAdminRead, status_code=status.HTTP_201_CREATED)
async def add_platform_admin(
    payload: PlatformAdminCreate,
    admin: Annotated[PlatformAdmin, Depends(require_role(ROLE_SUPER_ADMIN))],
    session: Annotated[AsyncSession, Depends(get_session)],
    request: Request,
):
    created = await platform_admin_service.add_admin(
        session, payload.email, added_by=admin.email, role=payload.role
    )
    await audit_service.record_action(
        session,
        actor=admin,
        action="platform_admin.add",
        target_type="platform_admin",
        target_id=created.id,
        after={"email": created.email, "role": created.role},
        ip_address=request.client.host if request.client else None,
    )
    return created


@router.patch("/{admin_id}/role", response_model=PlatformAdminRead)
async def update_platform_admin_role(
    admin_id: str,
    payload: PlatformAdminRoleUpdate,
    admin: Annotated[PlatformAdmin, Depends(require_role(ROLE_SUPER_ADMIN))],
    session: Annotated[AsyncSession, Depends(get_session)],
    request: Request,
):
    updated = await platform_admin_service.set_role(session, admin_id, payload.role)
    await audit_service.record_action(
        session,
        actor=admin,
        action="platform_admin.set_role",
        target_type="platform_admin",
        target_id=updated.id,
        after={"email": updated.email, "role": updated.role},
        ip_address=request.client.host if request.client else None,
    )
    return updated


@router.delete("/{admin_id}", response_model=PlatformAdminRead)
async def revoke_platform_admin(
    admin_id: str,
    admin: Annotated[PlatformAdmin, Depends(require_role(ROLE_SUPER_ADMIN))],
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


# ---- Permission management (sub-admin grants) ----

@router.get("/{admin_id}/permissions", response_model=list[AdminPermissionRead])
async def list_admin_permissions(
    admin_id: str,
    admin: Annotated[PlatformAdmin, Depends(require_permission(PERMISSION_ADMINS_READ))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    return await platform_admin_service.list_permissions(session, admin_id)


@router.post("/{admin_id}/permissions", response_model=AdminPermissionRead, status_code=status.HTTP_201_CREATED)
async def grant_admin_permission(
    admin_id: str,
    payload: AdminPermissionCreate,
    admin: Annotated[PlatformAdmin, Depends(require_role(ROLE_SUPER_ADMIN))],
    session: Annotated[AsyncSession, Depends(get_session)],
    request: Request,
):
    if not is_valid_permission(payload.permission):
        from fastapi import HTTPException

        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown permission")
    grant = await platform_admin_service.grant_permission(
        session, admin_id, payload.permission, granted_by=admin.email
    )
    await audit_service.record_action(
        session,
        actor=admin,
        action="platform_admin.grant_permission",
        target_type="platform_admin",
        target_id=admin_id,
        after={"permission": grant.permission},
        ip_address=request.client.host if request.client else None,
    )
    return grant


@router.delete("/{admin_id}/permissions/{permission}", response_model=AdminPermissionRead)
async def revoke_admin_permission(
    admin_id: str,
    permission: str,
    admin: Annotated[PlatformAdmin, Depends(require_role(ROLE_SUPER_ADMIN))],
    session: Annotated[AsyncSession, Depends(get_session)],
    request: Request,
):
    grant = await platform_admin_service.revoke_permission(session, admin_id, permission)
    await audit_service.record_action(
        session,
        actor=admin,
        action="platform_admin.revoke_permission",
        target_type="platform_admin",
        target_id=admin_id,
        after={"permission": grant.permission},
        ip_address=request.client.host if request.client else None,
    )
    return grant