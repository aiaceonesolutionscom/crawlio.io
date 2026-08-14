export const ADMIN_PERMISSIONS = [
  { key: 'dashboard.read', label: 'View dashboard', group: 'General' },
  { key: 'workspaces.read', label: 'View workspaces', group: 'Workspaces' },
  { key: 'workspaces.write', label: 'Edit / delete workspaces', group: 'Workspaces' },
  { key: 'plan_configs.read', label: 'View plans & limits', group: 'Plans' },
  { key: 'plan_configs.write', label: 'Edit plans & limits', group: 'Plans' },
  { key: 'platform_admins.read', label: 'View platform admins', group: 'Admins' },
  { key: 'platform_admins.write', label: 'Manage admin permissions', group: 'Admins' },
  { key: 'audit.read', label: 'View audit log', group: 'Audit' },
  { key: 'feature_flags.read', label: 'View feature flags', group: 'Feature flags' },
  { key: 'feature_flags.write', label: 'Edit feature flags', group: 'Feature flags' },
  { key: 'system_settings.read', label: 'View system settings', group: 'Settings' },
  { key: 'system_settings.write', label: 'Edit system settings', group: 'Settings' },
  { key: 'integrations.read', label: 'View API keys & integrations', group: 'Integrations' },
  { key: 'integrations.write', label: 'Edit API keys & integrations', group: 'Integrations' }
] as const;

export type AdminPermissionKey = (typeof ADMIN_PERMISSIONS)[number]['key'];

export const ADMIN_ROLES = [
  { key: 'super_admin', label: 'Super Admin', description: 'Full access to everything.' },
  { key: 'sub_admin', label: 'Sub Admin', description: 'Only what you explicitly grant below.' }
] as const;