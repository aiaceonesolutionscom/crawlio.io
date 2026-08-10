from fastapi import APIRouter, Depends

from app.api.v1.admin import (
    audit_log,
    dashboard,
    feature_flags,
    plan_configs,
    platform_admins,
    system_settings,
    whoami,
    workspaces,
)
from app.core.admin_deps import require_super_admin

# The require_super_admin guard is declared once here, at the aggregator level,
# so no future admin endpoint can accidentally ship unprotected.
admin_router = APIRouter(prefix="/admin", dependencies=[Depends(require_super_admin)])

admin_router.include_router(whoami.router)
admin_router.include_router(platform_admins.router)
admin_router.include_router(workspaces.router)
admin_router.include_router(plan_configs.router)
admin_router.include_router(audit_log.router)
admin_router.include_router(feature_flags.router)
admin_router.include_router(system_settings.router)
admin_router.include_router(dashboard.router)
