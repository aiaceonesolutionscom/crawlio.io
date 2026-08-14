import { apiFetch } from './client';

export interface BusinessProfileDTO {
  id: string;
  business_name: string;
  owner_name: string;
  business_phone: string | null;
  business_address: string | null;
  services: string;
  website: string | null;
  timezone: string;
  business_hours: Record<string, string[]>;
  knowledge_base: string;
  updated_at: string;
}

export interface EligibleLeadDTO {
  lead_id: string;
  name: string;
  company: string | null;
  email: string;
  website: string | null;
  source: string;
}

export interface OutreachUsageDTO {
  used: number;
  limit: number;
  remaining: number;
}

export interface OutreachDraftDTO {
  lead_id: string;
  recipient_name: string;
  recipient_company: string | null;
  recipient_email: string;
  source: string;
  subject: string;
  body: string;
}

export interface MeetingDTO {
  id: string;
  booking_ref: string;
  lead_name: string | null;
  lead_email: string | null;
  scheduled_at: string;
  status: string;
}

export interface ActivityDTO {
  id: string;
  conversation_id: string | null;
  whatsapp_conversation_id: string | null;
  stage: string;
  status: string;
  detail: string | null;
  created_at: string | null;
}

export const DEFAULT_HOURS = {
  monday: ['09:00', '18:00'],
  tuesday: ['09:00', '18:00'],
  wednesday: ['09:00', '18:00'],
  thursday: ['09:00', '18:00'],
  friday: ['09:00', '18:00'],
  saturday: ['10:00', '14:00'],
};

export function getBusinessProfile(token: string | null) {
  return apiFetch<BusinessProfileDTO | null>('/api/v1/business-profile', token);
}

export function createBusinessProfile(token: string | null, input: any) {
  return apiFetch<BusinessProfileDTO>('/api/v1/business-profile', token, {
    method: 'POST',
    body: JSON.stringify(input),
  });
}

export function updateBusinessProfile(token: string | null, input: any) {
  return apiFetch<BusinessProfileDTO>('/api/v1/business-profile', token, {
    method: 'PUT',
    body: JSON.stringify(input),
  });
}

export function getOutreachUsage(token: string | null) {
  return apiFetch<OutreachUsageDTO>('/api/v1/outreach/usage', token);
}

export function getEligibleLeads(token: string | null) {
  return apiFetch<EligibleLeadDTO[]>('/api/v1/outreach/eligible-leads', token);
}

export function generateOutreach(token: string | null, leadIds: string[]) {
  return apiFetch<OutreachDraftDTO[]>('/api/v1/outreach/generate', token, {
    method: 'POST',
    body: JSON.stringify({ lead_ids: leadIds }),
  });
}

export function regenerateOutreach(token: string | null, leadId: string) {
  return apiFetch<OutreachDraftDTO>('/api/v1/outreach/regenerate', token, {
    method: 'POST',
    body: JSON.stringify({ lead_id: leadId }),
  });
}

export function approveOutreach(token: string | null, items: { lead_id: string; subject: string; body: string }[]) {
  return apiFetch<{ sent: number; rejected: number; results: any[] }>('/api/v1/outreach/approve', token, {
    method: 'POST',
    body: JSON.stringify({ items }),
  });
}

export function listMeetings(token: string | null) {
  return apiFetch<MeetingDTO[]>('/api/v1/meetings', token);
}

export function getAgentActivity(token: string | null) {
  return apiFetch<ActivityDTO[]>('/api/v1/agent/activity', token);
}

export function editConversationReply(token: string | null, conversationId: string, reply: string) {
  return apiFetch<{ status: string; message: string }>(`/api/v1/conversations/${conversationId}/edit-reply`, token, {
    method: 'POST',
    body: JSON.stringify({ reply }),
  });
}

export function agentWsUrl(): string {
  const base = (import.meta.env.VITE_API_URL || '').replace(/^http/, 'ws').replace(/\/$/, '');
  return `${base}/api/v1/agent/ws`;
}