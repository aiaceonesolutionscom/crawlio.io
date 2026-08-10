import { apiFetch } from '../client';

export interface PlatformAdminDTO {
  id: string;
  email: string;
  clerk_user_id: string | null;
  added_by: string | null;
  is_active: boolean;
  created_at: string;
  revoked_at: string | null;
}

export function listPlatformAdmins(token: string | null) {
  return apiFetch<PlatformAdminDTO[]>('/api/v1/admin/platform-admins', token);
}

export function addPlatformAdmin(token: string | null, email: string) {
  return apiFetch<PlatformAdminDTO>('/api/v1/admin/platform-admins', token, {
    method: 'POST',
    body: JSON.stringify({ email })
  });
}

export function revokePlatformAdmin(token: string | null, adminId: string) {
  return apiFetch<PlatformAdminDTO>(`/api/v1/admin/platform-admins/${adminId}`, token, {
    method: 'DELETE'
  });
}
