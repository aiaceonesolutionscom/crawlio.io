import { apiFetch } from './client';
import type { LeadDTO } from './leads';

export interface AiFilterResponseDTO {
  with_website: LeadDTO[];
  without_website: LeadDTO[];
}

export function aiFilterLeads(token: string | null) {
  return apiFetch<AiFilterResponseDTO>('/api/v1/leads/ai-filter', token);
}

export interface CrmAddResultDTO {
  added: number;
  skipped: number;
}

export function addToCrm(token: string | null, leadIds: string[]) {
  return apiFetch<CrmAddResultDTO>('/api/v1/crm/entries', token, {
    method: 'POST',
    body: JSON.stringify({ lead_ids: leadIds })
  });
}

export interface CrmEntryDTO {
  id: string;
  lead: LeadDTO;
  category: 'with_website' | 'no_website';
  added_at: string;
}

export interface CrmEntryListResponseDTO {
  items: CrmEntryDTO[];
  total: number;
}

export function listCrmEntries(token: string | null) {
  return apiFetch<CrmEntryListResponseDTO>('/api/v1/crm/entries', token);
}
