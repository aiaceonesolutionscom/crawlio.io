import { apiFetch } from '../client';

export interface SystemSettingDTO {
  id: string;
  key: string;
  value: unknown;
  value_type: string;
  description: string | null;
  updated_by: string | null;
  updated_at: string;
}

export function listSystemSettings(token: string | null) {
  return apiFetch<SystemSettingDTO[]>('/api/v1/admin/system-settings', token);
}

export function upsertSystemSetting(
  token: string | null,
  key: string,
  input: { value: unknown; value_type: string; description?: string }
) {
  return apiFetch<SystemSettingDTO>(`/api/v1/admin/system-settings/${encodeURIComponent(key)}`, token, {
    method: 'PUT',
    body: JSON.stringify(input)
  });
}

export function deleteSystemSetting(token: string | null, key: string) {
  return apiFetch<void>(`/api/v1/admin/system-settings/${encodeURIComponent(key)}`, token, { method: 'DELETE' });
}
