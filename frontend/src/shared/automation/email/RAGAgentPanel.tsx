import React, { useCallback, useEffect, useState } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { Loader2Icon, SendIcon, StopCircleIcon, PlayIcon, SparklesIcon, CheckIcon } from 'lucide-react';
import { cn } from '../../utils/cn';
import {
  initializeAgent,
  sendAgentMessage,
  getConversationHistory,
  previewAgentOutreach,
  approveAgentOutreach,
  stopAgent,
  resumeAgent,
  type EmailConversationDTO,
  type EmailConversationMessageDTO,
  type EmailDraftDTO,
} from '../../../lib/api/emailAgent';
import { ApiError } from '../../../lib/api/client';

interface Props {
  emailAccountId: string;
  leadId?: string;
  leadName?: string;
  leadCompany?: string;
  leadEmail?: string;
}

export function RAGAgentPanel({ emailAccountId, leadId, leadName, leadCompany, leadEmail }: Props) {
  const { getToken } = useAuth();
  const [conversation, setConversation] = useState<EmailConversationDTO | null>(null);
  const [messages, setMessages] = useState<EmailConversationMessageDTO[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isInitializing, setIsInitializing] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  const [previewDraft, setPreviewDraft] = useState<EmailDraftDTO | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const fetchMessages = useCallback(async () => {
    if (!conversation) return;
    try {
      const token = await getToken();
      const msgs = await getConversationHistory(token, conversation.id);
      setMessages(msgs);
    } catch (err) {
      console.error('Failed to fetch messages:', err);
    }
  }, [getToken, conversation]);

  useEffect(() => {
    if (conversation) {
      void fetchMessages();
    }
  }, [conversation]);

  const handleInitialize = async () => {
    setIsInitializing(true);
    setError(null);
    try {
      const token = await getToken();
      const conv = await initializeAgent(token, {
        email_account_id: emailAccountId,
        lead_id: leadId,
        subject: leadName ? `Outreach to ${leadName}` : 'Outreach Conversation',
        lead_name: leadName,
        lead_email: leadEmail,
      });
      setConversation(conv);
      setSuccess('Agent session started! Tell me about your business.');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to initialize agent.');
    } finally {
      setIsInitializing(false);
    }
  };

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || !conversation) return;

    setIsSending(true);
    setError(null);

    try {
      const token = await getToken();
      const userMsg: EmailConversationMessageDTO = {
        id: `temp-${Date.now()}`,
        conversation_id: conversation.id,
        sender_type: 'user',
        content: inputMessage,
        is_approved: false,
        sent_at: null,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMsg]);
      setInputMessage('');

      const res = await sendAgentMessage(token, {
        conversation_id: conversation.id,
        message: inputMessage,
      });

      const aiMsg: EmailConversationMessageDTO = {
        id: `temp-ai-${Date.now()}`,
        conversation_id: conversation.id,
        sender_type: 'ai',
        content: res.response,
        is_approved: false,
        sent_at: null,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, aiMsg]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to send message.');
    } finally {
      setIsSending(false);
    }
  };

  const handlePreview = async () => {
    if (!conversation) return;

    setIsPreviewing(true);
    setError(null);

    try {
      const token = await getToken();
      const draft = await previewAgentOutreach(token, conversation.id);
      setPreviewDraft(draft);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to generate preview.');
    } finally {
      setIsPreviewing(false);
    }
  };

  const handleApprove = async () => {
    if (!conversation) return;

    setIsApproving(true);
    setError(null);

    try {
      const token = await getToken();
      await approveAgentOutreach(token, conversation.id);
      setSuccess('Outreach email sent successfully!');
      setPreviewDraft(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to send outreach.');
    } finally {
      setIsApproving(false);
    }
  };

  const handleStop = async () => {
    if (!conversation) return;
    try {
      const token = await getToken();
      await stopAgent(token, conversation.id);
      setConversation((prev) => prev ? { ...prev, ai_agent_active: false, status: 'paused' } : null);
      setSuccess('Agent paused.');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to stop agent.');
    }
  };

  const handleResume = async () => {
    if (!conversation) return;
    try {
      const token = await getToken();
      await resumeAgent(token, conversation.id);
      setConversation((prev) => prev ? { ...prev, ai_agent_active: true, status: 'active' } : null);
      setSuccess('Agent resumed.');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to resume agent.');
    }
  };

  if (!conversation) {
    return (
      <div className="rounded-2xl border border-ink-800 bg-ink-900 p-6">
        <div className="text-center">
          <SparklesIcon className="mx-auto h-10 w-10 text-signal" />
          <h3 className="mt-3 text-[16px] font-medium text-chalk">AI Email Agent</h3>
          <p className="mt-2 text-[13px] text-chalk-dim">
            Initialize the agent to start collecting business information and generating personalized outreach.
          </p>
          {leadName && (
            <p className="mt-2 text-[12px] text-chalk-faint">
              Target: {leadName}{leadCompany ? ` at ${leadCompany}` : ''}
            </p>
          )}
          <button
            onClick={handleInitialize}
            disabled={isInitializing}
            className="mt-4 flex h-9 items-center gap-2 rounded-lg border border-signal/50 bg-signal/10 px-4 text-[13px] text-signal hover:bg-signal/20 disabled:opacity-50 mx-auto"
          >
            {isInitializing ? <Loader2Icon className="h-4 w-4 animate-spin" /> : <PlayIcon className="h-4 w-4" />}
            {isInitializing ? 'Starting...' : 'Start Agent'}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col rounded-2xl border border-ink-800 bg-ink-900">
      <div className="flex items-center justify-between border-b border-ink-800 px-4 py-3">
        <div className="flex items-center gap-2">
          <div className={cn(
            'h-2 w-2 rounded-full',
            conversation.ai_agent_active ? 'bg-signal animate-pulse' : 'bg-ink-600'
          )} />
          <span className="text-[13px] font-medium text-chalk">
            AI Agent {conversation.ai_agent_active ? 'Active' : 'Paused'}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {conversation.ai_agent_active ? (
            <button
              onClick={handleStop}
              className="flex h-7 items-center gap-1 rounded-lg border border-ink-700 bg-ink-850 px-2 text-[11px] text-chalk-dim hover:border-ink-600"
            >
              <StopCircleIcon className="h-3 w-3" />
              Stop
            </button>
          ) : (
            <button
              onClick={handleResume}
              className="flex h-7 items-center gap-1 rounded-lg border border-signal/30 bg-signal/10 px-2 text-[11px] text-signal hover:bg-signal/20"
            >
              <PlayIcon className="h-3 w-3" />
              Resume
            </button>
          )}
          <button
            onClick={handlePreview}
            disabled={isPreviewing}
            className="flex h-7 items-center gap-1 rounded-lg border border-signal/50 bg-signal/10 px-2 text-[11px] text-signal hover:bg-signal/20 disabled:opacity-50"
          >
            {isPreviewing ? <Loader2Icon className="h-3 w-3 animate-spin" /> : <SparklesIcon className="h-3 w-3" />}
            Preview Outreach
          </button>
        </div>
      </div>

      {error && (
        <div className="mx-4 mt-3 rounded-lg border border-ember/40 bg-ember/10 px-3 py-2 text-[12px] text-ember">
          {error}
        </div>
      )}

      {success && (
        <div className="mx-4 mt-3 rounded-lg border border-signal/40 bg-signal/10 px-3 py-2 text-[12px] text-signal">
          {success}
        </div>
      )}

      {previewDraft && (
        <div className="mx-4 mt-3 rounded-lg border border-signal/30 bg-signal/5 p-4">
          <p className="mb-2 text-[12px] font-medium text-signal">Outreach Preview</p>
          <div className="space-y-2">
            <div>
              <p className="text-[11px] text-chalk-faint">Subject</p>
              <p className="text-[13px] text-chalk">{previewDraft.subject}</p>
            </div>
            <div>
              <p className="text-[11px] text-chalk-faint">Body</p>
              <div
                className="mt-1 rounded-lg border border-ink-700 bg-ink-950 p-3 text-[12px] text-chalk-dim max-h-40 overflow-y-auto"
                dangerouslySetInnerHTML={{ __html: previewDraft.body }}
              />
            </div>
          </div>
          <div className="mt-3 flex justify-end gap-2">
            <button
              onClick={() => setPreviewDraft(null)}
              className="flex h-7 items-center rounded-lg border border-ink-700 bg-ink-850 px-3 text-[11px] text-chalk hover:border-ink-600"
            >
              Cancel
            </button>
            <button
              onClick={handleApprove}
              disabled={isApproving}
              className="flex h-7 items-center gap-1 rounded-lg border border-signal/50 bg-signal/10 px-3 text-[11px] text-signal hover:bg-signal/20 disabled:opacity-50"
            >
              {isApproving ? <Loader2Icon className="h-3 w-3 animate-spin" /> : <CheckIcon className="h-3 w-3" />}
              {isApproving ? 'Sending...' : 'Approve & Send'}
            </button>
          </div>
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-4 space-y-3 max-h-[400px]">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={cn(
              'flex',
              msg.sender_type === 'user' ? 'justify-end' : 'justify-start'
            )}
          >
            <div
              className={cn(
                'max-w-[80%] rounded-lg px-3 py-2 text-[13px]',
                msg.sender_type === 'user'
                  ? 'bg-signal/10 text-chalk'
                  : 'bg-ink-850 text-chalk-dim'
              )}
            >
              {msg.content}
            </div>
          </div>
        ))}
        {isSending && (
          <div className="flex justify-start">
            <div className="bg-ink-850 rounded-lg px-3 py-2 text-[13px] text-chalk-dim">
              <Loader2Icon className="h-4 w-4 animate-spin" />
            </div>
          </div>
        )}
      </div>

      <div className="border-t border-ink-800 p-3">
        <div className="flex gap-2">
          <input
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && void handleSendMessage()}
            placeholder="Tell me about your business..."
            className="flex-1 h-9 rounded-lg border border-ink-700 bg-ink-950 px-3 text-[13px] text-chalk placeholder:text-chalk-faint focus:border-signal focus:outline-none"
            disabled={!conversation.ai_agent_active}
          />
          <button
            onClick={handleSendMessage}
            disabled={!inputMessage.trim() || isSending || !conversation.ai_agent_active}
            className="flex h-9 items-center gap-1 rounded-lg border border-signal/50 bg-signal/10 px-3 text-[13px] text-signal hover:bg-signal/20 disabled:opacity-50"
          >
            <SendIcon className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
