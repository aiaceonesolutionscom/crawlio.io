import { apiFetch } from './client';
import type { LeadStatus } from '../../types';

export interface LeadDTO {
  id: string;
  workspace_id: string;
  name: string;
  company: string | null;
  email: string | null;
  phone: string | null;
  score: number | null;
  status: LeadStatus;
  source: string | null;
  created_at: string;
  updated_at: string;
}

export interface LeadListResponseDTO {
  items: LeadDTO[];
  total: number;
}

export function listLeads(token: string | null, search?: string) {
  const query = search ? `?search=${encodeURIComponent(search)}` : '';
  return apiFetch<LeadListResponseDTO>(`/api/v1/leads${query}`, token);
}

export interface CreateLeadInput {
  name: string;
  company?: string;
  email?: string;
  phone?: string;
  source?: string;
}

export function createLead(token: string | null, input: CreateLeadInput) {
  return apiFetch<LeadDTO>('/api/v1/leads', token, {
    method: 'POST',
    body: JSON.stringify(input)
  });
}
