from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin_deps import require_permission
from app.core.permissions import PERMISSION_FEATURE_FLAGS_READ, PERMISSION_FEATURE_FLAGS_WRITE
from app.db.models.feature_flag import FeatureFlag, FeatureFlagOverride
from app.db.models.platform_admin import PlatformAdmin
from app.db.session import get_session
from app.schemas.admin import (
    FeatureFlagCreate,
    FeatureFlagOverrideRead,
    FeatureFlagOverrideSet,
    FeatureFlagRead,
    FeatureFlagUpdate,
)
from app.services.admin import audit_service, feature_flag_service

router = APIRouter(prefix="/feature-flags", tags=["admin:feature-flags"])


def _flag_snapshot(flag: FeatureFlag) -> dict:
    return {"key": flag.key, "description": flag.description, "default_enabled": flag.default_enabled}


def _override_snapshot(override: FeatureFlagOverride) -> dict:
    return {"is_enabled": override.is_enabled}


@router.get("", response_model=list[FeatureFlagRead])
async def list_feature_flags(
    admin: Annotated[PlatformAdmin, Depends(require_permission(PERMISSION_FEATURE_FLAGS_READ))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    return await feature_flag_service.list_flags(session)


@router.post("", response_model=FeatureFlagRead, status_code=201)
async def create_feature_flag(
    payload: FeatureFlagCreate,
    admin: Annotated[PlatformAdmin, Depends(require_permission(PERMISSION_FEATURE_FLAGS_WRITE))],
    session: Annotated[AsyncSession, Depends(get_session)],
    request: Request,
):
    flag = await feature_flag_service.create_flag(
        session, key=payload.key, description=payload.description, default_enabled=payload.default_enabled
    )
    await audit_service.record_action(
        session,
        actor=admin,
        action="feature_flag.create",
        target_type="feature_flag",
        target_id=flag.id,
        after=_flag_snapshot(flag),
        ip_address=request.client.host if request.client else None,
    )
    return flag


@router.patch("/{flag_id}", response_model=FeatureFlagRead)
async def update_feature_flag(
    flag_id: str,
    payload: FeatureFlagUpdate,
    admin: Annotated[PlatformAdmin, Depends(require_permission(PERMISSION_FEATURE_FLAGS_WRITE))],
    session: Annotated[AsyncSession, Depends(get_session)],
    request: Request,
):
    existing = await feature_flag_service.get_flag_or_404(session, flag_id)
    before = _flag_snapshot(existing)
    updated = await feature_flag_service.update_flag(session, flag_id, **payload.model_dump())
    await audit_service.record_action(
        session,
        actor=admin,
        action="feature_flag.update",
        target_type="feature_flag",
        target_id=flag_id,
        before=before,
        after=_flag_snapshot(updated),
        ip_address=request.client.host if request.client else None,
    )
    return updated


@router.delete("/{flag_id}", status_code=204)
async def delete_feature_flag(
    flag_id: str,
    admin: Annotated[PlatformAdmin, Depends(require_permission(PERMISSION_FEATURE_FLAGS_WRITE))],
    session: Annotated[AsyncSession, Depends(get_session)],
    request: Request,
):
    flag = await feature_flag_service.get_flag_or_404(session, flag_id)
    before = _flag_snapshot(flag)
    await feature_flag_service.delete_flag(session, flag)
    await audit_service.record_action(
        session,
        actor=admin,
        action="feature_flag.delete",
        target_type="feature_flag",
        target_id=flag_id,
        before=before,
        ip_address=request.client.host if request.client else None,
    )


@router.get("/{flag_id}/overrides", response_model=list[FeatureFlagOverrideRead])
async def list_feature_flag_overrides(
    flag_id: str,
    admin: Annotated[PlatformAdmin, Depends(require_permission(PERMISSION_FEATURE_FLAGS_READ))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    await feature_flag_service.get_flag_or_404(session, flag_id)
    return await feature_flag_service.list_overrides_for_flag(session, flag_id)


@router.put("/{flag_id}/overrides", response_model=FeatureFlagOverrideRead)
async def set_feature_flag_override(
    flag_id: str,
    payload: FeatureFlagOverrideSet,
    admin: Annotated[PlatformAdmin, Depends(require_permission(PERMISSION_FEATURE_FLAGS_WRITE))],
    session: Annotated[AsyncSession, Depends(get_session)],
    request: Request,
):
    await feature_flag_service.get_flag_or_404(session, flag_id)
    before_override = await feature_flag_service.get_override(session, flag_id, payload.workspace_id)
    before = _override_snapshot(before_override) if before_override else None
    updated = await feature_flag_service.set_override(
        session, flag_id=flag_id, workspace_id=payload.workspace_id, is_enabled=payload.is_enabled
    )
    await audit_service.record_action(
        session,
        actor=admin,
        action="feature_flag.override.set",
        target_type="feature_flag_override",
        target_id=flag_id,
        workspace_id=payload.workspace_id,
        before=before,
        after=_override_snapshot(updated),
        ip_address=request.client.host if request.client else None,
    )
    return updated


@router.delete("/{flag_id}/overrides/{workspace_id}", status_code=204)
async def clear_feature_flag_override(
    flag_id: str,
    workspace_id: str,
    admin: Annotated[PlatformAdmin, Depends(require_permission(PERMISSION_FEATURE_FLAGS_WRITE))],
    session: Annotated[AsyncSession, Depends(get_session)],
    request: Request,
):
    await feature_flag_service.get_flag_or_404(session, flag_id)
    await feature_flag_service.clear_override(session, flag_id, workspace_id)
    await audit_service.record_action(
        session,
        actor=admin,
        action="feature_flag.override.clear",
        target_type="feature_flag_override",
        target_id=flag_id,
        workspace_id=workspace_id,
        ip_address=request.client.host if request.client else None,
    )
