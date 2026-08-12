import { apiFetch } from './client';

export interface DiscoveredLeadDTO {
  name: string;
  phone: string | null;
  email: string | null;
  website: string | null;
  address: string | null;
  lat: number | null;
  lon: number | null;
  industry: string | null;
  social_links: Record<string, string>;
  source: string;
  rating: number | null;
  review_count: number | null;
  category: string | null;
  hours: string | null;
  plus_code: string | null;
  completeness: number | null;
  cache_hit: boolean;
  cached_at: string | null;
  result_city: string | null;
  is_fallback_city: boolean;
  already_in_workspace: boolean;
}

export interface DiscoverParams {
  niche: string;
  country: string;
  city: string;
  lat: number;
  lon: number;
  limit?: number;
}

export interface DiscoverResponseDTO {
  items: DiscoveredLeadDTO[];
  total: number;
  limit: number;
  enhanced: boolean;
  daily_limit: number;
  remaining_today: number;
}

export function suggestNiches(token: string | null, q?: string) {
  const query = q ? `?q=${encodeURIComponent(q)}` : '';
  return apiFetch<{ items: string[] }>(`/api/v1/leads/discover/niches${query}`, token);
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
