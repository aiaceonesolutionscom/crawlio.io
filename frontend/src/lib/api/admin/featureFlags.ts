import { apiFetch } from '../client';

export interface FeatureFlagDTO {
  id: string;
  key: string;
  description: string | null;
  default_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface FeatureFlagOverrideDTO {
  id: string;
  flag_id: string;
  workspace_id: string;
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export function listFeatureFlags(token: string | null) {
  return apiFetch<FeatureFlagDTO[]>('/api/v1/admin/feature-flags', token);
}

export function createFeatureFlag(
  token: string | null,
  input: { key: string; description?: string; default_enabled?: boolean }
) {
  return apiFetch<FeatureFlagDTO>('/api/v1/admin/feature-flags', token, {
    method: 'POST',
    body: JSON.stringify(input)
  });
}

export function updateFeatureFlag(
  token: string | null,
  flagId: string,
  input: { description?: string; default_enabled?: boolean }
) {
  return apiFetch<FeatureFlagDTO>(`/api/v1/admin/feature-flags/${flagId}`, token, {
    method: 'PATCH',
    body: JSON.stringify(input)
  });
}

export function deleteFeatureFlag(token: string | null, flagId: string) {
  return apiFetch<void>(`/api/v1/admin/feature-flags/${flagId}`, token, { method: 'DELETE' });
}

export function listOverrides(token: string | null, flagId: string) {
  return apiFetch<FeatureFlagOverrideDTO[]>(`/api/v1/admin/feature-flags/${flagId}/overrides`, token);
}

export function setOverride(token: string | null, flagId: string, workspaceId: string, isEnabled: boolean) {
  return apiFetch<FeatureFlagOverrideDTO>(`/api/v1/admin/feature-flags/${flagId}/overrides`, token, {
    method: 'PUT',
    body: JSON.stringify({ workspace_id: workspaceId, is_enabled: isEnabled })
  });
}

export function clearOverride(token: string | null, flagId: string, workspaceId: string) {
  return apiFetch<void>(`/api/v1/admin/feature-flags/${flagId}/overrides/${workspaceId}`, token, {
    method: 'DELETE'
  });
}
