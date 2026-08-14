import {
  BarChart3Icon,
  LayoutDashboardIcon,
  SettingsIcon,
  UsersIcon,
  WorkflowIcon,
  ZapIcon } from
'lucide-react';
import type { PlanId } from '../../types';
import type { LucideIcon } from 'lucide-react';

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  end?: boolean;
  locked?: boolean;
}

const ICONS = {
  dashboard: LayoutDashboardIcon,
  leads: ZapIcon,
  automation: WorkflowIcon,
  analytics: BarChart3Icon,
  team: UsersIcon,
  settings: SettingsIcon,
} as const;

export function buildNav(tier: PlanId): NavItem[] {
  const base = `/app/${tier}`;
  const freeOnly = tier === 'free';
  const items: NavItem[] = [
    { to: base, label: 'Dashboard', icon: ICONS.dashboard, end: true },
    { to: `${base}/leads`, label: 'Leads', icon: ICONS.leads },
    { to: `${base}/automation`, label: 'Automation', icon: ICONS.automation, locked: freeOnly },
    { to: `${base}/analytics`, label: 'Analytics', icon: ICONS.analytics, locked: freeOnly },
    { to: `${base}/team`, label: 'Team', icon: ICONS.team, locked: freeOnly },
    { to: `${base}/settings`, label: 'Settings', icon: ICONS.settings },
  ];
  return items;
}
