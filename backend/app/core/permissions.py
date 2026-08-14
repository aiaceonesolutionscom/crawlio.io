"""Permission catalog for the platform admin RBAC (Super Admin / Sub Admin).

Permission keys are dot-scoped strings: ``<resource>.<action>``. A Super Admin
implicitly holds every permission in ``ALL_PERMISSIONS``; a Sub Admin holds only
the permissions explicitly granted to them (see ``admin_permissions`` table).

When adding a new admin endpoint, give it the narrowest permission you can
instead of defaulting to "all admins can do everything".
"""

PERMISSION_DASHBOARD_READ = "dashboard.read"

PERMISSION_WORKSPACES_READ = "workspaces.read"
PERMISSION_WORKSPACES_WRITE = "workspaces.write"

PERMISSION_PLAN_CONFIGS_READ = "plan_configs.read"
PERMISSION_PLAN_CONFIGS_WRITE = "plan_configs.write"

PERMISSION_ADMINS_READ = "platform_admins.read"
PERMISSION_ADMINS_WRITE = "platform_admins.write"

PERMISSION_AUDIT_READ = "audit.read"

PERMISSION_FEATURE_FLAGS_READ = "feature_flags.read"
PERMISSION_FEATURE_FLAGS_WRITE = "feature_flags.write"

PERMISSION_SYSTEM_SETTINGS_READ = "system_settings.read"
PERMISSION_SYSTEM_SETTINGS_WRITE = "system_settings.write"

PERMISSION_INTEGRATIONS_READ = "integrations.read"
PERMISSION_INTEGRATIONS_WRITE = "integrations.write"

ALL_PERMISSIONS: frozenset[str] = frozenset(
    {
        PERMISSION_DASHBOARD_READ,
        PERMISSION_WORKSPACES_READ,
        PERMISSION_WORKSPACES_WRITE,
        PERMISSION_PLAN_CONFIGS_READ,
        PERMISSION_PLAN_CONFIGS_WRITE,
        PERMISSION_ADMINS_READ,
        PERMISSION_ADMINS_WRITE,
        PERMISSION_AUDIT_READ,
        PERMISSION_FEATURE_FLAGS_READ,
        PERMISSION_FEATURE_FLAGS_WRITE,
        PERMISSION_SYSTEM_SETTINGS_READ,
        PERMISSION_SYSTEM_SETTINGS_WRITE,
        PERMISSION_INTEGRATIONS_READ,
        PERMISSION_INTEGRATIONS_WRITE,
    }
)

ROLE_SUPER_ADMIN = "super_admin"
ROLE_SUB_ADMIN = "sub_admin"
ADMIN_ROLES = {ROLE_SUPER_ADMIN, ROLE_SUB_ADMIN}


def is_valid_permission(permission: str) -> bool:
    return permission in ALL_PERMISSIONS


def permissions_for_role(role: str) -> set[str]:
    """Super admin gets everything; sub admin starts with nothing (grants only)."""
    if role == ROLE_SUPER_ADMIN:
        return set(ALL_PERMISSIONS)
    return set()
