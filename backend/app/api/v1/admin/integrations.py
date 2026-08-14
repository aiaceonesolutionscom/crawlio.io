from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin_deps import require_permission
from app.core.permissions import PERMISSION_INTEGRATIONS_READ, PERMISSION_INTEGRATIONS_WRITE
from app.db.models.platform_admin import PlatformAdmin
from app.db.session import get_session
from app.schemas.admin import IntegrationRead, IntegrationTestResult, IntegrationOverrideUpsert
from app.services.admin import audit_service, integration_service

router = APIRouter(prefix="/integrations", tags=["admin:integrations"])


def _snapshot(row: dict) -> dict:
    return {"configured": row["configured"], "source": row["source"]}


@router.get("", response_model=list[IntegrationRead])
async def list_integrations(
    admin: Annotated[PlatformAdmin, Depends(require_permission(PERMISSION_INTEGRATIONS_READ))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    return await integration_service.list_integrations(session)


@router.put("/{key}", response_model=IntegrationRead)
async def set_integration_override(
    key: str,
    payload: IntegrationOverrideUpsert,
    admin: Annotated[PlatformAdmin, Depends(require_permission(PERMISSION_INTEGRATIONS_WRITE))],
    session: Annotated[AsyncSession, Depends(get_session)],
    request: Request,
):
    item = integration_service.get_integration(key)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Unknown integration: {key}")
    before = await integration_service._override_value(session, key)
    updated = await integration_service.set_override(
        session, key=key, value=payload.value, updated_by=admin.email
    )
    await audit_service.record_action(
        session,
        actor=admin,
        action="integration.override.set",
        target_type="integration",
        target_id=key,
        before={"has_override": bool(before)},
        after=_snapshot(updated),
        ip_address=request.client.host if request.client else None,
    )
    return updated


@router.delete("/{key}", response_model=IntegrationRead)
async def clear_integration_override(
    key: str,
    admin: Annotated[PlatformAdmin, Depends(require_permission(PERMISSION_INTEGRATIONS_WRITE))],
    session: Annotated[AsyncSession, Depends(get_session)],
    request: Request,
):
    item = integration_service.get_integration(key)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Unknown integration: {key}")
    before = await integration_service._override_value(session, key)
    updated = await integration_service.clear_override(session, key=key, updated_by=admin.email)
    await audit_service.record_action(
        session,
        actor=admin,
        action="integration.override.clear",
        target_type="integration",
        target_id=key,
        before={"has_override": bool(before)},
        after=_snapshot(updated),
        ip_address=request.client.host if request.client else None,
    )
    return updated


@router.post("/{key}/test", response_model=IntegrationTestResult)
async def test_integration(
    key: str,
    admin: Annotated[PlatformAdmin, Depends(require_permission(PERMISSION_INTEGRATIONS_READ))],
):
    return await integration_service.run_test(key)
