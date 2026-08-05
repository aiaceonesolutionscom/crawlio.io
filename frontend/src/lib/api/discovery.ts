import { apiFetch } from './client';

export interface DiscoveredLeadDTO {
  name: string;
  phone: string | null;
  email: string | null;
  website: string | null;
  address: string | null;
  source: string;
}

export interface DiscoverParams {
  niche: string;
  country: string;
  city: string;
  lat: number;
  lon: number;
}

export interface DiscoverResponseDTO {
  items: DiscoveredLeadDTO[];
  total: number;
  limit: number;
  enhanced: boolean;
}

export function discoverLeads(token: string | null, params: DiscoverParams) {
  return apiFetch<DiscoverResponseDTO>('/api/v1/leads/discover', token, {
    method: 'POST',
    body: JSON.stringify(params)
  });
}

export interface DiscoveryImportSkip {
  name: string;
  reason: string;
}

export interface DiscoveryImportResultDTO {
  created: unknown[];
  skipped: DiscoveryImportSkip[];
}

export function importDiscoveredLeads(token: string | null, items: DiscoveredLeadDTO[]) {
  return apiFetch<DiscoveryImportResultDTO>('/api/v1/leads/discover/import', token, {
    method: 'POST',
    body: JSON.stringify({ items })
  });
}
