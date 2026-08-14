from typing import Annotated, Any, Callable, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import ALL_PERMISSIONS, ROLE_SUPER_ADMIN, is_valid_permission
from app.core.security import verify_clerk_jwt
from app.db.models.admin_permission import AdminPermission
from app.db.models.platform_admin import PlatformAdmin
from app.db.session import get_session
from app.services.admin.platform_admin_service import resolve_or_bootstrap

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_claims(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer_scheme)]
) -> dict[str, Any]:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    return verify_clerk_jwt(credentials.credentials)


async def get_current_admin(
    claims: Annotated[dict[str, Any], Depends(get_current_claims)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PlatformAdmin:
    admin = await resolve_or_bootstrap(session, claims)
    if admin is None or not admin.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return admin


async def get_admin_permissions(session: AsyncSession, admin: PlatformAdmin) -> set[str]:
    """Effective permission set: super admins implicitly hold every permission;
    sub admins get the union of their explicit grants."""
    if admin.role == ROLE_SUPER_ADMIN:
        return set(ALL_PERMISSIONS)
    result = await session.execute(
        select(AdminPermission.permission).where(AdminPermission.admin_id == admin.id)
    )
    return {row[0] for row in result.all()}


def require_permission(permission: str) -> Callable[[PlatformAdmin, AsyncSession], PlatformAdmin]:
    """Dependency factory: requires the current admin to hold `permission`.

    Usage:
        admin: Annotated[PlatformAdmin, Depends(require_permission(PERMISSION_X))]
    """
    if not is_valid_permission(permission):
        raise ValueError(f"Unknown permission: {permission}")

    async def _guard(
        admin: Annotated[PlatformAdmin, Depends(get_current_admin)],
        session: Annotated[AsyncSession, Depends(get_session)],
    ) -> PlatformAdmin:
        perms = await get_admin_permissions(session, admin)
        if permission not in perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {permission}",
            )
        return admin

    return _guard


def require_role(*roles: str) -> Callable[[PlatformAdmin, AsyncSession], PlatformAdmin]:
    """Dependency factory: restricts to admins whose role is in `roles`."""

    async def _guard(
        admin: Annotated[PlatformAdmin, Depends(get_current_admin)],
    ) -> PlatformAdmin:
        if admin.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role: {' or '.join(roles)}",
            )
        return admin

    return _guard