import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.permissions import ROLE_SUPER_ADMIN, ADMIN_ROLES
from app.db.models.admin_permission import AdminPermission
from app.db.models.platform_admin import PlatformAdmin

logger = logging.getLogger(__name__)


async def get_by_clerk_user_id(session: AsyncSession, clerk_user_id: str) -> Optional[PlatformAdmin]:
    result = await session.execute(
        select(PlatformAdmin).where(PlatformAdmin.clerk_user_id == clerk_user_id, PlatformAdmin.is_active.is_(True))
    )
    return result.scalar_one_or_none()


async def get_by_email(session: AsyncSession, email: str) -> Optional[PlatformAdmin]:
    result = await session.execute(select(PlatformAdmin).where(PlatformAdmin.email == email.lower()))
    return result.scalar_one_or_none()


async def resolve_or_bootstrap(session: AsyncSession, claims: dict[str, Any]) -> Optional[PlatformAdmin]:
    """Resolves the caller to an active PlatformAdmin, auto-provisioning one from
    the SUPER_ADMIN_EMAILS env allowlist on first sight. Returns None if the
    caller isn't (and isn't allowlisted to become) a platform admin.
    """
    clerk_user_id = claims["sub"]

    admin = await get_by_clerk_user_id(session, clerk_user_id)
    if admin is not None:
        return admin

    email = claims.get("email")
    if not email:
        logger.warning(
            "Clerk token for sub=%s has no 'email' claim (claim keys present: %s) — "
            "add a custom session-token claim in the Clerk Dashboard "
            "(Sessions -> Customize session token -> {\"email\": \"{{user.primary_email_address}}\"}) "
            "before admin bootstrap can work.",
            clerk_user_id,
            list(claims.keys()),
        )
        return None
    email = email.lower()

    # Pre-provisioned by another admin via the panel, logging in for the first time.
    existing = await get_by_email(session, email)
    if existing is not None and existing.is_active:
        if existing.clerk_user_id is None:
            existing.clerk_user_id = clerk_user_id
            await session.commit()
            await session.refresh(existing)
        return existing

    if existing is None and email in {e.lower() for e in settings.super_admin_emails}:
        bootstrapped = PlatformAdmin(
            email=email, clerk_user_id=clerk_user_id, added_by="system:bootstrap", is_active=True
        )
        session.add(bootstrapped)
        await session.commit()
        await session.refresh(bootstrapped)
        return bootstrapped

    return None


async def list_admins(session: AsyncSession) -> list[PlatformAdmin]:
    result = await session.execute(select(PlatformAdmin).order_by(PlatformAdmin.created_at))
    return list(result.scalars().all())


async def count_active_admins(session: AsyncSession) -> int:
    admins = await list_admins(session)
    return sum(1 for a in admins if a.is_active)


async def add_admin(session: AsyncSession, email: str, added_by: str, role: str = ROLE_SUPER_ADMIN) -> PlatformAdmin:
    email = email.lower()
    if role not in ADMIN_ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid role: {role}")
    existing = await get_by_email(session, email)
    if existing is not None:
        existing.is_active = True
        existing.revoked_at = None
        existing.role = role
        await session.commit()
        await session.refresh(existing)
        return existing

    admin = PlatformAdmin(email=email, added_by=added_by, is_active=True, role=role)
    session.add(admin)
    await session.commit()
    await session.refresh(admin)
    return admin


async def revoke_admin(session: AsyncSession, admin_id: str) -> PlatformAdmin:
    result = await session.execute(select(PlatformAdmin).where(PlatformAdmin.id == admin_id))
    admin = result.scalar_one_or_none()
    if admin is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin not found")

    if admin.is_active and await count_active_admins(session) <= 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot revoke the last active admin")

    admin.is_active = False
    admin.revoked_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(admin)
    return admin


async def set_role(session: AsyncSession, admin_id: str, role: str) -> PlatformAdmin:
    if role not in ADMIN_ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid role: {role}")
    result = await session.execute(select(PlatformAdmin).where(PlatformAdmin.id == admin_id))
    admin = result.scalar_one_or_none()
    if admin is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin not found")
    admin.role = role
    if role == ROLE_SUPER_ADMIN:
        # Promoting to super admin makes grants moot; drop them.
        await session.execute(delete(AdminPermission).where(AdminPermission.admin_id == admin.id))
    await session.commit()
    await session.refresh(admin)
    return admin


async def grant_permission(session: AsyncSession, admin_id: str, permission: str, granted_by: str) -> AdminPermission:
    result = await session.execute(select(PlatformAdmin).where(PlatformAdmin.id == admin_id))
    admin = result.scalar_one_or_none()
    if admin is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin not found")
    if admin.role == ROLE_SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Super admins implicitly hold every permission; no grant needed",
        )
    existing = await session.execute(
        select(AdminPermission).where(
            AdminPermission.admin_id == admin_id, AdminPermission.permission == permission
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Permission already granted")
    grant = AdminPermission(admin_id=admin_id, permission=permission, granted_by=granted_by)
    session.add(grant)
    await session.commit()
    await session.refresh(grant)
    return grant


async def revoke_permission(session: AsyncSession, admin_id: str, permission: str) -> AdminPermission:
    result = await session.execute(
        select(AdminPermission).where(
            AdminPermission.admin_id == admin_id, AdminPermission.permission == permission
        )
    )
    grant = result.scalar_one_or_none()
    if grant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission not granted")
    await session.delete(grant)
    await session.commit()
    return grant


async def list_permissions(session: AsyncSession, admin_id: str) -> list[AdminPermission]:
    result = await session.execute(
        select(AdminPermission).where(AdminPermission.admin_id == admin_id).order_by(AdminPermission.permission)
    )
    return list(result.scalars().all())
