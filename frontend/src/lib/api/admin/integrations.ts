import { apiFetch } from '../client';

export interface IntegrationDTO {
  key: string;
  label: string;
  description: string;
  env_name: string;
  configured: boolean;
  source: 'override' | 'env' | 'unset';
  masked_value: string;
}

export interface IntegrationTestResultDTO {
  ok: boolean;
  message: string;
}

export function listIntegrations(token: string | null) {
  return apiFetch<IntegrationDTO[]>('/api/v1/admin/integrations', token);
}

export function setIntegrationOverride(token: string | null, key: string, value: string) {
  return apiFetch<IntegrationDTO>(`/api/v1/admin/integrations/${encodeURIComponent(key)}`, token, {
    method: 'PUT',
    body: JSON.stringify({ value })
  });
}

export function clearIntegrationOverride(token: string | null, key: string) {
  return apiFetch<IntegrationDTO>(`/api/v1/admin/integrations/${encodeURIComponent(key)}`, token, {
    method: 'DELETE'
  });
}

export function testIntegration(token: string | null, key: string) {
  return apiFetch<IntegrationTestResultDTO>(
    `/api/v1/admin/integrations/${encodeURIComponent(key)}/test`,
    token,
    { method: 'POST' }
  );
}