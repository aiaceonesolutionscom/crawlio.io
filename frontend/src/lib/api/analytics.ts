import { apiFetch } from './client';

export interface WeekBucketDTO {
  week: string;
  leads: number;
  qualified: number;
}

export interface SourceSliceDTO {
  name: string;
  value: number;
}

export interface StatusCountDTO {
  status: string;
  count: number;
}

export interface AnalyticsOverviewDTO {
  total_leads: number;
  qualified_leads: number;
  avg_score: number;
  leads_over_time: WeekBucketDTO[];
  source_split: SourceSliceDTO[];
  status_breakdown: StatusCountDTO[];
}

export function getAnalyticsOverview(token: string | null) {
  return apiFetch<AnalyticsOverviewDTO>('/api/v1/analytics/overview', token);
}
