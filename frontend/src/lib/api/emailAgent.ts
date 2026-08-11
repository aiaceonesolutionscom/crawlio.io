import { apiFetch } from './client';

export interface EmailAccountDTO {
  id: string;
  workspace_id: string;
  user_id: string;
  email_address: string;
  display_name: string | null;
  provider: string;
  is_active: boolean;
  daily_sent_count: number;
  last_synced_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface EmailAccountListResponseDTO {
  items: EmailAccountDTO[];
}

export interface EmailAccountConnectResponseDTO {
  auth_url: string;
}

export interface EmailDraftDTO {
  id: string;
  workspace_id: string;
  email_account_id: string;
  lead_id: string | null;
  subject: string;
  body: string;
  kind: string;
  status: string;
  recipient_emails: string | null;
  ai_prompt: string | null;
  conversation_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface EmailDraftListResponseDTO {
  items: EmailDraftDTO[];
}

export interface EmailQuotaDTO {
  composed_count: number;
  ai_generated_count: number;
  total_sent: number;
  limit: number;
  remaining: number;
}

export interface EmailConversationDTO {
  id: string;
  workspace_id: string;
  email_account_id: string;
  lead_id: string | null;
  lead_name?: string;
  lead_email?: string;
  subject: string;
  status: string;
  ai_agent_active: boolean;
  thread_id?: string | null;
  business_context: string | null;
  customer_email?: string | null;
  customer_name?: string | null;
  created_at: string;
  updated_at: string;
}

export interface EmailConversationMessageDTO {
  id: string;
  conversation_id: string;
  sender_type: string;
  content: string;
  is_approved: boolean;
  sent_at: string | null;
  created_at: string;
}

export interface EmailMessageDTO {
  id: string;
  thread_id: string | null;
  subject: string;
  from_email: string;
  to_email: string;
  date: string;
  body: string;
  body_preview: string;
  snippet: string;
  label_ids: string[];
  is_read: boolean;
  is_customer_interested?: boolean;
  has_conversation?: boolean;
}

export interface EmailMessageListResponseDTO {
  items: EmailMessageDTO[];
  page: number;
  page_size: number;
  total: number;
  has_more: boolean;
}

export function getGoogleAuthUrl(token: string | null) {
  return apiFetch<EmailAccountConnectResponseDTO>('/api/v1/email-accounts/connect/google', token);
}

export function listEmailAccounts(token: string | null) {
  return apiFetch<EmailAccountListResponseDTO>('/api/v1/email-accounts', token);
}

export function disconnectEmailAccount(token: string | null, accountId: string) {
  return apiFetch<undefined>(`/api/v1/email-accounts/${accountId}`, token, {
    method: 'DELETE',
  });
}

export function getEmailQuota(token: string | null, accountId: string) {
  return apiFetch<EmailQuotaDTO>(`/api/v1/email-accounts/${accountId}/quota`, token);
}

export function createEmailDraft(token: string | null, input: {
  email_account_id: string;
  subject: string;
  body: string;
  kind?: string;
  recipient_emails?: string[];
  lead_id?: string;
  ai_prompt?: string;
  conversation_id?: string;
}) {
  return apiFetch<EmailDraftDTO>('/api/v1/email-drafts', token, {
    method: 'POST',
    body: JSON.stringify(input),
  });
}

export function updateEmailDraft(token: string | null, draftId: string, input: {
  subject?: string;
  body?: string;
  recipient_emails?: string[];
}) {
  return apiFetch<EmailDraftDTO>(`/api/v1/email-drafts/${draftId}`, token, {
    method: 'PATCH',
    body: JSON.stringify(input),
  });
}

export function sendEmailDraft(token: string | null, draftId: string) {
  return apiFetch<{ status: string; email_message_id: string }>(`/api/v1/email-drafts/${draftId}/send`, token, {
    method: 'POST',
  });
}

export function listEmailDrafts(token: string | null, status?: string) {
  const query = status ? `?status_filter=${status}` : '';
  return apiFetch<EmailDraftListResponseDTO>(`/api/v1/email-drafts${query}`, token);
}

export function generateAIEmail(token: string | null, input: {
  email_account_id: string;
  prompt: string;
  lead_id?: string;
  lead_name?: string;
  lead_company?: string;
  lead_email?: string;
}) {
  return apiFetch<EmailDraftDTO>('/api/v1/email-ai/generate', token, {
    method: 'POST',
    body: JSON.stringify(input),
  });
}

export function approveAIEmail(token: string | null, draftId: string) {
  return apiFetch<{ status: string; email_message_id: string }>(`/api/v1/email-ai/approve/${draftId}`, token, {
    method: 'POST',
  });
}

export function initializeAgent(token: string | null, input: {
  email_account_id: string;
  lead_id?: string;
  subject?: string;
  lead_name?: string;
  lead_email?: string;
}) {
  return apiFetch<EmailConversationDTO>('/api/v1/email-agent/initialize', token, {
    method: 'POST',
    body: JSON.stringify(input),
  });
}

export function sendAgentMessage(token: string | null, input: {
  conversation_id: string;
  message: string;
}) {
  return apiFetch<{ response: string }>('/api/v1/email-agent/message', token, {
    method: 'POST',
    body: JSON.stringify(input),
  });
}

export function getConversationHistory(token: string | null, conversationId: string) {
  return apiFetch<EmailConversationMessageDTO[]>(`/api/v1/email-agent/conversation/${conversationId}`, token);
}

export function previewAgentOutreach(token: string | null, conversationId: string) {
  return apiFetch<EmailDraftDTO>(`/api/v1/email-agent/preview/${conversationId}`, token, {
    method: 'POST',
  });
}

export function approveAgentOutreach(token: string | null, conversationId: string) {
  return apiFetch<{ status: string; email_message_id: string }>(`/api/v1/email-agent/approve/${conversationId}`, token, {
    method: 'POST',
  });
}

export function stopAgent(token: string | null, conversationId: string) {
  return apiFetch<{ status: string }>(`/api/v1/email-agent/stop/${conversationId}`, token, {
    method: 'POST',
  });
}

export function resumeAgent(token: string | null, conversationId: string) {
  return apiFetch<{ status: string }>(`/api/v1/email-agent/resume/${conversationId}`, token, {
    method: 'POST',
  });
}

export function processInboundReplies(token: string | null, accountId: string) {
  return apiFetch<{ processed: number; results: { conversation_id: string; result: any }[] }>(
    `/api/v1/email-agent/process-inbound/${accountId}`, token, {
      method: 'POST',
    }
  );
}

export interface ConversationStartRequest {
  email_account_id: string;
  email_id: string;
  lead_name?: string;
  lead_email?: string;
  thread_id?: string | null;
}

export interface ConversationMessageRequest {
  conversation_id: string;
  message: string;
  sender_type?: 'user' | 'ai' | 'system';
}

export interface BookingRequest {
  email_account_id: string;
  conversation_id?: string;
  lead_name: string;
  lead_email: string;
  lead_company?: string;
  meeting_datetime: string;
}

export interface BusinessInfoRequest {
  email_account_id: string;
  conversation_id: string;
  business_name: string;
  business_subject: string;
  business_additional_info?: string;
}

export interface ConversationWithMessages {
  conversation: {
    id: string;
    workspace_id: string;
    email_account_id: string;
    lead_id: string | null;
    subject: string;
    status: string;
    ai_agent_active: boolean;
    thread_id?: string | null;
    business_context: string | null;
    customer_email?: string | null;
    customer_name?: string | null;
    created_at: string;
    updated_at: string;
  };
  messages: EmailConversationMessageDTO[];
}

export interface ConversationListResponse {
  items: EmailConversationDTO[];
}

export function startConversation(token: string | null, input: ConversationStartRequest) {
  return apiFetch<EmailConversationDTO>('/api/v1/email-conversations/start', token, {
    method: 'POST',
    body: JSON.stringify(input),
  });
}

export function sendConversationMessage(token: string | null, input: ConversationMessageRequest) {
  return apiFetch<EmailConversationMessageDTO>(`/api/v1/email-conversations/${input.conversation_id}/messages`, token, {
    method: 'POST',
    body: JSON.stringify({ message: input.message, sender_type: input.sender_type }),
  });
}

export function sendManualReply(token: string | null, conversationId: string, message: string) {
  return apiFetch<{ status: string; message: string }>(`/api/v1/email-conversations/${conversationId}/reply`, token, {
    method: 'POST',
    body: JSON.stringify({
      conversation_id: conversationId,
      message,
      sender_type: 'user',
    }),
  });
}

export function stopConversation(token: string | null, conversationId: string) {
  return apiFetch<{ status: string }>(`/api/v1/email-conversations/${conversationId}/stop`, token, {
    method: 'POST',
  });
}

export function resumeConversation(token: string | null, conversationId: string) {
  return apiFetch<{ status: string }>(`/api/v1/email-conversations/${conversationId}/resume`, token, {
    method: 'POST',
  });
}

export function getConversation(token: string | null, conversationId: string) {
  return apiFetch<ConversationWithMessages>(`/api/v1/email-conversations/${conversationId}`, token);
}

export function bookMeeting(token: string | null, input: BookingRequest) {
  return apiFetch<{ booking_ref: string; lead_name: string; lead_email: string; lead_company: string; meeting_datetime: string; lead_id: string | null }>(
    '/api/v1/email-conversations/book-meeting', token, {
      method: 'POST',
      body: JSON.stringify(input),
    }
  );
}

export function saveBusinessInfo(
  token: string | null,
  accountId: string,
  conversationId: string,
  input: Omit<BusinessInfoRequest, 'email_account_id' | 'conversation_id'>,
) {
  return apiFetch<{ status: string; business_context: any }>(
    `/api/v1/email-conversations/${conversationId}/business-info`, token, {
      method: 'POST',
      body: JSON.stringify({
        email_account_id: accountId,
        conversation_id: conversationId,
        ...input,
      }),
    }
  );
}

export function getActiveConversations(token: string | null, accountId: string) {
  return apiFetch<ConversationListResponse>(`/api/v1/email-conversations/accounts/${accountId}/active`, token);
}

export function downloadBookedLeadsCsv(token: string | null) {
  return fetch(`${import.meta.env.VITE_API_URL}/api/v1/email-conversations/booked-leads/export`, {
    headers: {
      'Authorization': token ? `Bearer ${token}` : '',
    },
  }).then(res => res.blob());
}

export function checkAccountQuota(token: string | null, accountId: string) {
  return apiFetch<EmailQuotaDTO>(`/api/v1/email-conversations/accounts/${accountId}/quota`, token);
}
