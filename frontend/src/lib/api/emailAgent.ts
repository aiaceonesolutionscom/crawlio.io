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
  subject: string;
  status: string;
  ai_agent_active: boolean;
  business_context: string | null;
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
}

export interface EmailMessageListResponseDTO {
  items: EmailMessageDTO[];
}

export function getGoogleAuthUrl(token: string | null) {
  return apiFetch<EmailAccountConnectResponseDTO>('/api/v1/email-accounts/connect/google', token);
}

export function getMicrosoftAuthUrl(token: string | null) {
  return apiFetch<EmailAccountConnectResponseDTO>('/api/v1/email-accounts/connect/microsoft', token);
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
