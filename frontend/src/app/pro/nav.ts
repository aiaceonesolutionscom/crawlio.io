import {
  BarChart3Icon,
  LayoutDashboardIcon,
  SettingsIcon,
  UsersIcon,
  WorkflowIcon,
  ZapIcon } from
'lucide-react';

export const NAV = [
{ to: '/app/pro', label: 'Dashboard', icon: LayoutDashboardIcon, end: true },
{ to: '/app/pro/leads', label: 'Leads', icon: ZapIcon },
{ to: '/app/pro/automation', label: 'Automation', icon: WorkflowIcon },
{ to: '/app/pro/analytics', label: 'Analytics', icon: BarChart3Icon },
{ to: '/app/pro/team', label: 'Team', icon: UsersIcon },
{ to: '/app/pro/settings', label: 'Settings', icon: SettingsIcon }];
