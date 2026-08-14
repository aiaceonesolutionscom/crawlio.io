from fastapi import APIRouter, Depends

from app.api.v1.admin import (
    audit_log,
    dashboard,
    feature_flags,
    integrations,
    plan_configs,
    platform_admins,
    system_settings,
    whoami,
    workspaces,
)
from app.core.admin_deps import get_current_admin

# Only require a valid, active admin here at the aggregator level; each endpoint
# applies its own fine-grained permission guard via require_permission(...).
admin_router = APIRouter(prefix="/admin", dependencies=[Depends(get_current_admin)])

admin_router.include_router(whoami.router)
admin_router.include_router(platform_admins.router)
admin_router.include_router(workspaces.router)
admin_router.include_router(plan_configs.router)
admin_router.include_router(audit_log.router)
admin_router.include_router(feature_flags.router)
admin_router.include_router(system_settings.router)
admin_router.include_router(integrations.router)
admin_router.include_router(dashboard.router)
