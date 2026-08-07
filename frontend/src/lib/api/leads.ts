import { apiFetch } from './client';
import type { LeadStatus } from '../../types';

export interface LeadDTO {
  id: string;
  workspace_id: string;
  name: string;
  email: string | null;
  phone: string | null;
  website: string | null;
  address: string | null;
  industry: string | null;
  score: number | null;
  status: LeadStatus;
  source: string | null;
  scoring_failed: boolean;
  social_links: Record<string, string>;
  created_at: string;
  updated_at: string;
}

export interface LeadListResponseDTO {
  items: LeadDTO[];
  total: number;
  page: number;
  limit: number;
}

export interface ListLeadsParams {
  search?: string;
  page?: number;
  limit?: number;
}

function buildQuery(params?: ListLeadsParams) {
  const query = new URLSearchParams();
  if (params?.search) query.set('search', params.search);
  if (params?.page) query.set('page', String(params.page));
  if (params?.limit) query.set('limit', String(params.limit));
  const qs = query.toString();
  return qs ? `?${qs}` : '';
}

export function listLeads(token: string | null, params?: ListLeadsParams) {
  return apiFetch<LeadListResponseDTO>(`/api/v1/leads${buildQuery(params)}`, token);
}

export function getLead(token: string | null, id: string) {
  return apiFetch<LeadDTO>(`/api/v1/leads/${id}`, token);
}

export interface CreateLeadInput {
  name: string;
  email?: string;
  phone?: string;
  website?: string;
  address?: string;
  industry?: string;
  social_links?: Record<string, string>;
  source?: string;
}

export interface UpdateLeadInput {
  name?: string;
  email?: string;
  phone?: string;
  website?: string;
  address?: string;
  industry?: string;
  social_links?: Record<string, string>;
  status?: LeadStatus;
  source?: string;
}

export function createLead(token: string | null, input: CreateLeadInput) {
  return apiFetch<LeadDTO>('/api/v1/leads', token, {
    method: 'POST',
    body: JSON.stringify(input)
  });
}

export function updateLead(token: string | null, id: string, input: UpdateLeadInput) {
  return apiFetch<LeadDTO>(`/api/v1/leads/${id}`, token, {
    method: 'PATCH',
    body: JSON.stringify(input)
  });
}

export function deleteLead(token: string | null, id: string) {
  return apiFetch<void>(`/api/v1/leads/${id}`, token, { method: 'DELETE' });
}

export function deleteAllLeads(token: string | null) {
  return apiFetch<{ deleted: number }>('/api/v1/leads', token, { method: 'DELETE' });
}

export function enrichLeads(token: string | null, leadIds: string[]) {
  return apiFetch<{ enriched: number; unchanged: number }>('/api/v1/leads/enrich', token, {
    method: 'POST',
    body: JSON.stringify({ lead_ids: leadIds })
  });
}

export function sendLeadEmail(token: string | null, id: string) {
  return apiFetch<{ sent: boolean }>(`/api/v1/leads/${id}/email`, token, { method: 'POST' });
}

export function sendLeadWhatsApp(token: string | null, id: string) {
  return apiFetch<{ url: string }>(`/api/v1/leads/${id}/whatsapp`, token, { method: 'POST' });
}

export async function exportLeads(token: string | null, search?: string) {
  const query = search ? `?search=${encodeURIComponent(search)}` : '';
  const API_URL = import.meta.env.VITE_API_URL;
  const res = await fetch(`${API_URL}/api/v1/leads/export${query}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {}
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(body || res.statusText);
  }
  return res.blob();
}
