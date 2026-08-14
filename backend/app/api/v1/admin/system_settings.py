from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin_deps import require_permission
from app.core.permissions import PERMISSION_SYSTEM_SETTINGS_READ, PERMISSION_SYSTEM_SETTINGS_WRITE
from app.db.models.platform_admin import PlatformAdmin
from app.db.models.system_setting import SystemSetting
from app.db.session import get_session
from app.schemas.admin import SystemSettingRead, SystemSettingUpsert
from app.services.admin import audit_service, system_setting_service

router = APIRouter(prefix="/system-settings", tags=["admin:system-settings"])


def _snapshot(setting: SystemSetting) -> dict:
    return {"value": setting.value, "value_type": setting.value_type, "description": setting.description}


@router.get("", response_model=list[SystemSettingRead])
async def list_system_settings(
    admin: Annotated[PlatformAdmin, Depends(require_permission(PERMISSION_SYSTEM_SETTINGS_READ))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    return await system_setting_service.list_settings(session)


@router.put("/{key}", response_model=SystemSettingRead)
async def upsert_system_setting(
    key: str,
    payload: SystemSettingUpsert,
    admin: Annotated[PlatformAdmin, Depends(require_permission(PERMISSION_SYSTEM_SETTINGS_WRITE))],
    session: Annotated[AsyncSession, Depends(get_session)],
    request: Request,
):
    existing = await system_setting_service.get_setting(session, key)
    before = _snapshot(existing) if existing else None
    updated = await system_setting_service.upsert_setting(
        session,
        key=key,
        value=payload.value,
        value_type=payload.value_type,
        description=payload.description,
        updated_by=admin.email,
    )
    await audit_service.record_action(
        session,
        actor=admin,
        action="system_setting.upsert",
        target_type="system_setting",
        target_id=key,
        before=before,
        after=_snapshot(updated),
        ip_address=request.client.host if request.client else None,
    )
    return updated


@router.delete("/{key}", status_code=204)
async def delete_system_setting(
    key: str,
    admin: Annotated[PlatformAdmin, Depends(require_permission(PERMISSION_SYSTEM_SETTINGS_WRITE))],
    session: Annotated[AsyncSession, Depends(get_session)],
    request: Request,
):
    existing = await system_setting_service.get_setting_or_404(session, key)
    before = _snapshot(existing)
    await system_setting_service.delete_setting(session, key)
    await audit_service.record_action(
        session,
        actor=admin,
        action="system_setting.delete",
        target_type="system_setting",
        target_id=key,
        before=before,
        ip_address=request.client.host if request.client else None,
    )
