import { apiFetch } from '../client';

export interface WhoamiDTO {
  email: string;
  role: string;
  is_super_admin: boolean;
  permissions: string[];
}

export function getWhoami(token: string | null) {
  return apiFetch<WhoamiDTO>('/api/v1/admin/whoami', token);
}