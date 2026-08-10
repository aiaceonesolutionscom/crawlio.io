import { apiFetch } from '../client';

export interface PlanConfigDTO {
  id: string;
  plan_key: string;
  display_name: string;
  lead_quota: number;
  seat_quota: number;
  discovery_result_limit: number;
  daily_discovery_import_limit: number;
  daily_email_limit: number;
  capabilities: string[];
  sort_order: number;
  is_active: boolean;
  updated_at: string;
}

export interface PlanConfigUpdateInput {
  display_name?: string;
  lead_quota?: number;
  seat_quota?: number;
  discovery_result_limit?: number;
  daily_discovery_import_limit?: number;
  daily_email_limit?: number;
  capabilities?: string[];
  sort_order?: number;
  is_active?: boolean;
}

export function listPlanConfigs(token: string | null) {
  return apiFetch<PlanConfigDTO[]>('/api/v1/admin/plan-configs', token);
}

export function updatePlanConfig(token: string | null, planKey: string, data: PlanConfigUpdateInput) {
  return apiFetch<PlanConfigDTO>(`/api/v1/admin/plan-configs/${planKey}`, token, {
    method: 'PATCH',
    body: JSON.stringify(data)
  });
}
