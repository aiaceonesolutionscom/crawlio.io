import { apiFetch } from '../client';

export interface PlanCountDTO {
  plan: string;
  count: number;
}

export interface WeekCountDTO {
  week: string;
  count: number;
}

export interface AdminDashboardOverviewDTO {
  total_workspaces: number;
  workspaces_by_plan: PlanCountDTO[];
  total_leads: number;
  new_workspaces_over_time: WeekCountDTO[];
  active_platform_admins: number;
}

export function getAdminDashboardOverview(token: string | null) {
  return apiFetch<AdminDashboardOverviewDTO>('/api/v1/admin/dashboard/overview', token);
}
