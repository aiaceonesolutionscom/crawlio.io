import { apiFetch } from './client';
import type { PlanId } from '../../types';

export interface WorkspaceDTO {
  id: string;
  name: string;
  plan: PlanId;
  lead_quota: number;
  seat_quota: number;
  created_at: string;
}

export function getMyWorkspace(token: string | null) {
  return apiFetch<WorkspaceDTO>('/api/v1/workspaces/me', token);
}

export function createWorkspace(token: string | null, name: string) {
  return apiFetch<WorkspaceDTO>('/api/v1/workspaces', token, {
    method: 'POST',
    body: JSON.stringify({ name })
  });
}

export function updateWorkspacePlan(token: string | null, workspaceId: string, plan: PlanId) {
  return apiFetch<WorkspaceDTO>(`/api/v1/workspaces/${workspaceId}/plan`, token, {
    method: 'PATCH',
    body: JSON.stringify({ plan })
  });
}
