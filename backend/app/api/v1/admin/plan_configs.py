from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin_deps import require_super_admin
from app.db.session import get_session
from app.db.models.plan_config import PlanConfig
from app.db.models.platform_admin import PlatformAdmin
from app.schemas.admin import PlanConfigRead, PlanConfigUpdate
from app.services import audit_service, plan_config_service

router = APIRouter(prefix="/plan-configs", tags=["admin:plan-configs"])


def _snapshot(config: PlanConfig) -> dict:
    return {
        "display_name": config.display_name,
        "lead_quota": config.lead_quota,
        "seat_quota": config.seat_quota,
        "discovery_result_limit": config.discovery_result_limit,
        "daily_discovery_import_limit": config.daily_discovery_import_limit,
        "daily_email_limit": config.daily_email_limit,
        "capabilities": config.capabilities,
        "sort_order": config.sort_order,
        "is_active": config.is_active,
    }


@router.get("", response_model=list[PlanConfigRead])
async def list_plan_configs(
    admin: Annotated[PlatformAdmin, Depends(require_super_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    return await plan_config_service.list_plan_configs(session)


@router.patch("/{plan_key}", response_model=PlanConfigRead)
async def update_plan_config(
    plan_key: str,
    payload: PlanConfigUpdate,
    admin: Annotated[PlatformAdmin, Depends(require_super_admin)],
    session: Annotated[AsyncSession, Depends(get_session)],
    request: Request,
):
    existing = await plan_config_service.get_plan_config_or_404(session, plan_key)
    before = _snapshot(existing)
    updated = await plan_config_service.update_plan_config(session, plan_key, **payload.model_dump())
    await audit_service.record_action(
        session,
        actor=admin,
        action="plan_config.update",
        target_type="plan_config",
        target_id=plan_key,
        before=before,
        after=_snapshot(updated),
        ip_address=request.client.host if request.client else None,
    )
    return updated
