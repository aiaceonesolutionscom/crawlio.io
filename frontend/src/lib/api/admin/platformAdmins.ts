import { apiFetch } from '../client';

export interface PlatformAdminDTO {
  id: string;
  email: string;
  role: string;
  clerk_user_id: string | null;
  added_by: string | null;
  is_active: boolean;
  created_at: string;
  revoked_at: string | null;
}

export interface AdminPermissionDTO {
  id: string;
  admin_id: string;
  permission: string;
  granted_by: string;
  created_at: string;
}

export function listPlatformAdmins(token: string | null) {
  return apiFetch<PlatformAdminDTO[]>('/api/v1/admin/platform-admins', token);
}

export function addPlatformAdmin(token: string | null, email: string, role = 'sub_admin') {
  return apiFetch<PlatformAdminDTO>('/api/v1/admin/platform-admins', token, {
    method: 'POST',
    body: JSON.stringify({ email, role })
  });
}

export function updatePlatformAdminRole(token: string | null, adminId: string, role: string) {
  return apiFetch<PlatformAdminDTO>(`/api/v1/admin/platform-admins/${adminId}/role`, token, {
    method: 'PATCH',
    body: JSON.stringify({ role })
  });
}

export function revokePlatformAdmin(token: string | null, adminId: string) {
  return apiFetch<PlatformAdminDTO>(`/api/v1/admin/platform-admins/${adminId}`, token, {
    method: 'DELETE'
  });
}

export function listAdminPermissions(token: string | null, adminId: string) {
  return apiFetch<AdminPermissionDTO[]>(`/api/v1/admin/platform-admins/${adminId}/permissions`, token);
}

export function grantAdminPermission(token: string | null, adminId: string, permission: string) {
  return apiFetch<AdminPermissionDTO>(`/api/v1/admin/platform-admins/${adminId}/permissions`, token, {
    method: 'POST',
    body: JSON.stringify({ permission })
  });
}

export function revokeAdminPermission(token: string | null, adminId: string, permission: string) {
  return apiFetch<AdminPermissionDTO>(
    `/api/v1/admin/platform-admins/${adminId}/permissions/${encodeURIComponent(permission)}`,
    token,
    { method: 'DELETE' }
  );
}