import { apiFetch } from '../client';

export interface AdminWorkspaceDTO {
  id: string;
  name: string;
  plan: string;
  lead_quota: number;
  seat_quota: number;
  webhook_token: string;
  created_at: string;
  member_count: number;
  lead_count: number;
  email_count: number;
}

export interface AdminWorkspaceUpdateInput {
  name?: string;
  plan?: string;
  lead_quota?: number;
  seat_quota?: number;
}

export function listWorkspaces(token: string | null, search?: string) {
  const query = search ? `?search=${encodeURIComponent(search)}` : '';
  return apiFetch<AdminWorkspaceDTO[]>(`/api/v1/admin/workspaces${query}`, token);
}

export function getWorkspace(token: string | null, workspaceId: string) {
  return apiFetch<AdminWorkspaceDTO>(`/api/v1/admin/workspaces/${workspaceId}`, token);
}

export function updateWorkspace(token: string | null, workspaceId: string, data: AdminWorkspaceUpdateInput) {
  return apiFetch<AdminWorkspaceDTO>(`/api/v1/admin/workspaces/${workspaceId}`, token, {
    method: 'PATCH',
    body: JSON.stringify(data)
  });
}

export function deleteWorkspace(token: string | null, workspaceId: string) {
  return apiFetch<undefined>(`/api/v1/admin/workspaces/${workspaceId}`, token, {
    method: 'DELETE'
  });
}
