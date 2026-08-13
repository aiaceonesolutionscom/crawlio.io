import { apiFetch } from './client';

export interface WhatsAppAccountDTO {
  id: string;
  workspace_id: string;
  user_id: string;
  phone_number_id: string;
  waba_id: string | null;
  business_phone: string | null;
  display_name: string | null;
  token_type: string;
  is_active: boolean;
  daily_sent_count: number;
  last_synced_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface WhatsAppAccountListResponseDTO {
  items: WhatsAppAccountDTO[];
}

export interface WhatsAppConnectResponseDTO {
  auth_url: string | null;
  test_mode: boolean;
}

export interface WhatsAppManualConnectRequest {
  phone_number_id: string;
  access_token: string;
  waba_id?: string | null;
  business_phone?: string | null;
  display_name?: string | null;
}

export interface WhatsAppQuotaDTO {
  sent_count: number;
  limit: number;
  remaining: number;
}

export interface WhatsAppConversationDTO {
  id: string;
  workspace_id: string;
  whatsapp_account_id: string;
  lead_id: string | null;
  status: string;
  ai_agent_active: boolean;
  business_context: string | null;
  customer_phone: string | null;
  customer_name: string | null;
  last_processed_message_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface WhatsAppConversationMessageDTO {
  id: string;
  conversation_id: string;
  sender_type: string;
  content: string;
  is_approved: boolean;
  sent_at: string | null;
  direction: string;
  provider_message_id: string | null;
  created_at: string;
}

export interface WhatsAppConversationPreviewDTO {
  id: string;
  customer_name: string | null;
  customer_phone: string | null;
  last_message: string;
  last_message_sender_type: string;
  last_message_at: string | null;
  ai_agent_active: boolean;
  status: string;
  is_booked: boolean;
  business_context: string | null;
}

export interface WhatsAppConversationPreviewListResponseDTO {
  items: WhatsAppConversationPreviewDTO[];
  page: number;
  page_size: number;
  has_more: boolean;
  total: number;
}

export interface WhatsAppConversationWithMessages {
  conversation: WhatsAppConversationDTO;
  messages: WhatsAppConversationMessageDTO[];
}

export interface WhatsAppStatsDTO {
  outreach_sent_today: number;
  inbound_received_today: number;
  ai_replies_today: number;
  meetings_booked_today: number;
  active_conversations: number;
  total_messages_today: number;
}

export interface WhatsAppBookingResponse {
  booking_ref: string;
  lead_name: string;
  lead_phone: string;
  lead_company: string;
  meeting_datetime: string;
  lead_id: string | null;
}

// ---- accounts ----

export function getWhatsAppConnect(token: string | null) {
  return apiFetch<WhatsAppConnectResponseDTO>('/api/v1/whatsapp-accounts/connect', token);
}

export function listWhatsAppAccounts(token: string | null) {
  return apiFetch<WhatsAppAccountListResponseDTO>('/api/v1/whatsapp-accounts', token);
}

export function connectWhatsAppManual(token: string | null, input: WhatsAppManualConnectRequest) {
  return apiFetch<WhatsAppAccountDTO>('/api/v1/whatsapp-accounts/connect', token, {
    method: 'POST',
    body: JSON.stringify(input),
  });
}

export function disconnectWhatsAppAccount(token: string | null, accountId: string) {
  return apiFetch<undefined>(`/api/v1/whatsapp-accounts/${accountId}`, token, {
    method: 'DELETE',
  });
}

export function getWhatsAppQuota(token: string | null, accountId: string) {
  return apiFetch<WhatsAppQuotaDTO>(`/api/v1/whatsapp-accounts/${accountId}/quota`, token);
}

// ---- conversations ----

export function getWhatsAppPreviews(
  token: string | null, accountId: string, page: number = 1, pageSize: number = 10
) {
  return apiFetch<WhatsAppConversationPreviewListResponseDTO>(
    `/api/v1/whatsapp-conversations/accounts/${accountId}/preview?page=${page}&page_size=${pageSize}`,
    token
  );
}

export function getWhatsAppConversation(token: string | null, conversationId: string) {
  return apiFetch<WhatsAppConversationWithMessages>(
    `/api/v1/whatsapp-conversations/${conversationId}`, token
  );
}

export function replyToWhatsAppConversation(token: string | null, conversationId: string, message: string) {
  return apiFetch<{ status: string; message: string; provider_message_id: string | null }>(
    `/api/v1/whatsapp-conversations/${conversationId}/reply`, token, {
      method: 'POST',
      body: JSON.stringify({ conversation_id: conversationId, message, sender_type: 'user' }),
    }
  );
}

export function stopWhatsAppAgent(token: string | null, conversationId: string) {
  return apiFetch<{ status: string }>(`/api/v1/whatsapp-conversations/${conversationId}/stop`, token, {
    method: 'POST',
  });
}

export function resumeWhatsAppAgent(token: string | null, conversationId: string) {
  return apiFetch<{ status: string }>(`/api/v1/whatsapp-conversations/${conversationId}/resume`, token, {
    method: 'POST',
  });
}

export function saveWhatsAppBusinessInfo(
  token: string | null,
  conversationId: string,
  input: { business_name: string; business_subject: string; business_additional_info?: string },
) {
  return apiFetch<{ status: string; business_context: any }>(
    `/api/v1/whatsapp-conversations/${conversationId}/business-info`, token, {
      method: 'POST',
      body: JSON.stringify({ conversation_id: conversationId, ...input }),
    }
  );
}

export function bookWhatsAppMeeting(
  token: string | null,
  input: { whatsapp_account_id: string; conversation_id?: string | null; lead_name: string; lead_phone: string; lead_company?: string; meeting_datetime: string },
) {
  return apiFetch<WhatsAppBookingResponse>('/api/v1/whatsapp-conversations/book-meeting', token, {
    method: 'POST',
    body: JSON.stringify(input),
  });
}

export function getWhatsAppStats(token: string | null, accountId: string) {
  return apiFetch<WhatsAppStatsDTO>(`/api/v1/whatsapp-conversations/accounts/${accountId}/stats`, token);
}

export function downloadWhatsAppBookedLeadsCsv(token: string | null) {
  return fetch(`${import.meta.env.VITE_API_URL}/api/v1/whatsapp-conversations/booked-leads/export`, {
    headers: {
      'Authorization': token ? `Bearer ${token}` : '',
    },
  }).then(res => res.blob());
}

// ---- outreach ----

export interface WhatsAppEligibleLeadDTO {
  lead_id: string;
  name: string;
  company: string | null;
  phone: string;
  website: string | null;
  source: string;
}

export interface WhatsAppOutreachUsageDTO {
  used: number;
  limit: number;
  remaining: number;
}

export interface WhatsAppOutreachDraftDTO {
  lead_id: string;
  recipient_name: string;
  recipient_company: string | null;
  recipient_phone: string;
  source: string;
  body: string;
}

export interface WhatsAppTemplateDTO {
  id: string;
  template_name: string;
  body: string;
  status: string;
  params: string;
}

export interface WhatsAppApproveResultDTO {
  lead_id: string;
  sent: boolean;
  status: string;
  template: string | null;
  error: string | null;
}

export function getWhatsAppOutreachUsage(token: string | null) {
  return apiFetch<WhatsAppOutreachUsageDTO>('/api/v1/whatsapp-outreach/usage', token);
}

export function getWhatsAppEligibleLeads(token: string | null) {
  return apiFetch<WhatsAppEligibleLeadDTO[]>('/api/v1/whatsapp-outreach/eligible-leads', token);
}

export function generateWhatsAppOutreach(token: string | null, leadIds: string[]) {
  return apiFetch<WhatsAppOutreachDraftDTO[]>('/api/v1/whatsapp-outreach/generate', token, {
    method: 'POST',
    body: JSON.stringify({ lead_ids: leadIds }),
  });
}

export function regenerateWhatsAppOutreach(token: string | null, leadId: string) {
  return apiFetch<WhatsAppOutreachDraftDTO>('/api/v1/whatsapp-outreach/regenerate', token, {
    method: 'POST',
    body: JSON.stringify({ lead_id: leadId }),
  });
}

export function approveWhatsAppOutreach(
  token: string | null, items: { lead_id: string; body: string }[]
) {
  return apiFetch<{ sent: number; pending: number; rejected: number; results: WhatsAppApproveResultDTO[] }>(
    '/api/v1/whatsapp-outreach/approve', token, {
      method: 'POST',
      body: JSON.stringify({ items }),
    }
  );
}

export function listWhatsAppTemplates(token: string | null) {
  return apiFetch<WhatsAppTemplateDTO[]>('/api/v1/whatsapp-outreach/templates', token);
}

export function syncWhatsAppTemplates(token: string | null) {
  return apiFetch<WhatsAppTemplateDTO[]>('/api/v1/whatsapp-outreach/templates/sync', token, {
    method: 'POST',
  });
}