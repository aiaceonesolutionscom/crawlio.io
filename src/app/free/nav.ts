import {
  BarChart3Icon,
  LayoutDashboardIcon,
  SettingsIcon,
  UsersIcon,
  WorkflowIcon,
  ZapIcon } from
'lucide-react';

export const NAV = [
{ to: '/app/free', label: 'Dashboard', icon: LayoutDashboardIcon, end: true },
{ to: '/app/free/leads', label: 'Leads', icon: ZapIcon },
{ to: '/app/free/automation', label: 'Automation', icon: WorkflowIcon, locked: true },
{ to: '/app/free/analytics', label: 'Analytics', icon: BarChart3Icon, locked: true },
{ to: '/app/free/team', label: 'Team', icon: UsersIcon, locked: true },
{ to: '/app/free/settings', label: 'Settings', icon: SettingsIcon }];
