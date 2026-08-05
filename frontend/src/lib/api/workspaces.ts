import { apiFetch } from './client';
import type { PlanId } from '../../types';

export interface WorkspaceDTO {
  id: string;
  name: string;
  plan: PlanId;
  lead_quota: number;
  seat_quota: number;
  leads_used: number;
  seats_used: number;
  created_at: string;
}

export function getMyWorkspace(token: string | null) {
  return apiFetch<WorkspaceDTO>('/api/v1/workspaces/me', token);
}

export function createWorkspace(token: string | null, name: string, ownerEmail?: string, ownerName?: string) {
  return apiFetch<WorkspaceDTO>('/api/v1/workspaces', token, {
    method: 'POST',
    body: JSON.stringify({ name, owner_email: ownerEmail, owner_name: ownerName })
  });
}

export function updateWorkspacePlan(token: string | null, workspaceId: string, plan: PlanId) {
  return apiFetch<WorkspaceDTO>(`/api/v1/workspaces/${workspaceId}/plan`, token, {
    method: 'PATCH',
    body: JSON.stringify({ plan })
  });
}
