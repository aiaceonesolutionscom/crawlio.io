from fastapi import APIRouter, Depends

from app.api.v1.admin import (
    audit_log,
    auth,
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

admin_router = APIRouter(prefix="/admin")

# Auth login endpoint - no admin check needed
admin_router.include_router(auth.router, dependencies=[])

# All other admin endpoints require admin auth
admin_router.include_router(whoami.router, dependencies=[Depends(get_current_admin)])
admin_router.include_router(platform_admins.router, dependencies=[Depends(get_current_admin)])
admin_router.include_router(workspaces.router, dependencies=[Depends(get_current_admin)])
admin_router.include_router(plan_configs.router, dependencies=[Depends(get_current_admin)])
admin_router.include_router(audit_log.router, dependencies=[Depends(get_current_admin)])
admin_router.include_router(feature_flags.router, dependencies=[Depends(get_current_admin)])
admin_router.include_router(system_settings.router, dependencies=[Depends(get_current_admin)])
admin_router.include_router(integrations.router, dependencies=[Depends(get_current_admin)])
admin_router.include_router(dashboard.router, dependencies=[Depends(get_current_admin)])
