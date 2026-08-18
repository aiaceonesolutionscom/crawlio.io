import { apiFetch } from '../client';

export interface AdminLoginResponse {
  token: string;
  username: string;
}

export function adminLogin(username: string, password: string) {
  return apiFetch<AdminLoginResponse>('/api/v1/admin/auth/login', null, {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
}
