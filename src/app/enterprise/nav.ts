import {
  BarChart3Icon,
  LayoutDashboardIcon,
  SettingsIcon,
  UsersIcon,
  WorkflowIcon,
  ZapIcon } from
'lucide-react';

export const NAV = [
{ to: '/app/enterprise', label: 'Dashboard', icon: LayoutDashboardIcon, end: true },
{ to: '/app/enterprise/leads', label: 'Leads', icon: ZapIcon },
{ to: '/app/enterprise/automation', label: 'Automation', icon: WorkflowIcon },
{ to: '/app/enterprise/analytics', label: 'Analytics', icon: BarChart3Icon },
{ to: '/app/enterprise/team', label: 'Team', icon: UsersIcon },
{ to: '/app/enterprise/settings', label: 'Settings', icon: SettingsIcon }];
