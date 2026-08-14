import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '@clerk/clerk-react';
import {
  ArrowLeftIcon, Loader2Icon, InboxIcon, SendIcon, SparklesIcon,
  StopCircleIcon, PlayIcon, CalendarIcon, DownloadIcon, XIcon,
  SearchIcon, PlusIcon, MessageCircleIcon, CheckIcon, EditIcon,
} from 'lucide-react';
import { cn } from '../utils/cn';
import { khiTime } from '../utils/time';
import { ApiError } from '../../lib/api/client';
import {
  getWhatsAppConnect, listWhatsAppAccounts, connectWhatsAppManual,
  getWhatsAppQuota, getWhatsAppPreviews, getWhatsAppConversation, replyToWhatsAppConversation,
  stopWhatsAppAgent, resumeWhatsAppAgent, bookWhatsAppMeeting, getWhatsAppStats,
  downloadWhatsAppBookedLeadsCsv,
  getWhatsAppOutreachUsage, getWhatsAppEligibleLeads, generateWhatsAppOutreach,
  regenerateWhatsAppOutreach, approveWhatsAppOutreach, listWhatsAppTemplates, syncWhatsAppTemplates,
  type WhatsAppAccountDTO, type WhatsAppQuotaDTO, type WhatsAppConversationDTO,
  type WhatsAppConversationMessageDTO, type WhatsAppConversationPreviewDTO, type WhatsAppStatsDTO,
  type WhatsAppOutreachUsageDTO, type WhatsAppEligibleLeadDTO, type WhatsAppOutreachDraftDTO,
  type WhatsAppTemplateDTO,
} from '../../lib/api/whatsapp';
import { getBusinessProfile, type BusinessProfileDTO } from '../../lib/api/agent';
import { BusinessOnboarding } from './BusinessOnboarding';
import { ActivityPanel } from './ActivityPanel';

export function WhatsAppAgentPage({ backTo }: { backTo: string }) {
  const { getToken } = useAuth();

  // Workspace gate
  const [profile, setProfile] = useState<BusinessProfileDTO | null>(null);
  const [profileLoading, setProfileLoading] = useState(true);
  const [showSetup, setShowSetup] = useState(false);

  // Accounts
  const [accounts, setAccounts] = useState<WhatsAppAccountDTO[]>([]);
  const [selectedAccount, setSelectedAccount] = useState<WhatsAppAccountDTO | null>(null);
  const [loadingAccounts, setLoadingAccounts] = useState(true);
  const [quota, setQuota] = useState<WhatsAppQuotaDTO | null>(null);
  const [stats, setStats] = useState<WhatsAppStatsDTO | null>(null);

  // Connect dialog
  const [connectOpen, setConnectOpen] = useState(false);
  const [testMode, setTestMode] = useState(false);
  const [authUrl, setAuthUrl] = useState<string | null>(null);
  const [manualForm, setManualForm] = useState({ phone_number_id: '', access_token: '', waba_id: '', business_phone: '', display_name: '' });
  const [connecting, setConnecting] = useState(false);

  // Inbox
  const [pageTab, setPageTab] = useState<'inbox' | 'outreach'>('inbox');
  const [previews, setPreviews] = useState<WhatsAppConversationPreviewDTO[]>([]);
  const [previewPage, setPreviewPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [loadingInbox, setLoadingInbox] = useState(false);
  const [search, setSearch] = useState('');
  const [conversation, setConversation] = useState<WhatsAppConversationDTO | null>(null);
  const [messages, setMessages] = useState<WhatsAppConversationMessageDTO[]>([]);
  const [manualReply, setManualReply] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [chatScrollRef, setChatScrollRef] = useState<HTMLDivElement | null>(null);

  // Booking
  const [bookingOpen, setBookingOpen] = useState(false);
  const [bookingForm, setBookingForm] = useState({ name: '', date: '', time: '' });

  // Outreach
  const [usage, setUsage] = useState<WhatsAppOutreachUsageDTO | null>(null);
  const [outreachLeads, setOutreachLeads] = useState<WhatsAppEligibleLeadDTO[]>([]);
  const [drafts, setDrafts] = useState<WhatsAppOutreachDraftDTO[]>([]);
  const [draftIdx, setDraftIdx] = useState(0);
  const [selectedLeads, setSelectedLeads] = useState<Set<string>>(new Set());
  const [generating, setGenerating] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [approving, setApproving] = useState(false);
  const [templates, setTemplates] = useState<WhatsAppTemplateDTO[]>([]);
  const [editingDraft, setEditingDraft] = useState(false);
  const [confirmSend, setConfirmSend] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (chatScrollRef) chatScrollRef.scrollTop = chatScrollRef.scrollHeight;
  }, [messages, chatScrollRef]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const token = await getToken();
        const res = await getBusinessProfile(token);
        if (!cancelled) setProfile(res);
      } catch {
        /* ignore */
      } finally {
        if (!cancelled) setProfileLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [getToken]);

  const fetchAccounts = useCallback(async () => {
    setLoadingAccounts(true);
    try {
      const token = await getToken();
      const res = await listWhatsAppAccounts(token);
      setAccounts(res.items);
      setSelectedAccount((prev) => prev && res.items.some((a) => a.id === prev.id) ? prev : (res.items[0] || null));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load WhatsApp accounts.');
    } finally {
      setLoadingAccounts(false);
    }
  }, [getToken]);

  useEffect(() => { void fetchAccounts(); }, [fetchAccounts]);

  const fetchQuotaAndStats = useCallback(async () => {
    if (!selectedAccount) return;
    const token = await getToken();
    getWhatsAppQuota(token, selectedAccount.id).then(setQuota).catch(() => undefined);
    getWhatsAppStats(token, selectedAccount.id).then(setStats).catch(() => undefined);
  }, [getToken, selectedAccount]);

  useEffect(() => { void fetchQuotaAndStats(); }, [fetchQuotaAndStats]);

  const fetchPreviews = useCallback(async () => {
    if (!selectedAccount) return;
    setLoadingInbox(true);
    try {
      const token = await getToken();
      const res = await getWhatsAppPreviews(token, selectedAccount.id, previewPage, 10);
      setPreviews(res.items);
      setHasMore(res.has_more ?? false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load conversations.');
    } finally {
      setLoadingInbox(false);
    }
  }, [getToken, selectedAccount, previewPage]);

  useEffect(() => { void fetchPreviews(); }, [fetchPreviews]);

  const fetchOutreach = useCallback(async () => {
    if (!selectedAccount) return;
    try {
      const token = await getToken();
      const [u, leads, templatesData] = await Promise.all([
        getWhatsAppOutreachUsage(token),
        getWhatsAppEligibleLeads(token),
        listWhatsAppTemplates(token),
      ]);
      setUsage(u);
      setOutreachLeads(leads);
      setTemplates(templatesData);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load outreach.');
    }
  }, [getToken, selectedAccount]);

  useEffect(() => {
    if (pageTab === 'outreach') void fetchOutreach();
  }, [pageTab]);

  const openConnect = useCallback(async () => {
    setError(null);
    try {
      const token = await getToken();
      const res = await getWhatsAppConnect(token);
      setTestMode(res.test_mode);
      setAuthUrl(res.auth_url);
      setConnectOpen(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to start connect.');
    }
  }, [getToken]);

  const handleEmbeddedConnect = () => {
    if (authUrl) window.location.href = authUrl;
  };

  const handleManualConnect = async () => {
    if (!manualForm.phone_number_id.trim() || !manualForm.access_token.trim()) {
      setError('Phone Number ID and Access Token are required.');
      return;
    }
    setConnecting(true);
    setError(null);
    try {
      const token = await getToken();
      await connectWhatsAppManual(token, {
        phone_number_id: manualForm.phone_number_id.trim(),
        access_token: manualForm.access_token.trim(),
        waba_id: manualForm.waba_id.trim() || null,
        business_phone: manualForm.business_phone.trim() || null,
        display_name: manualForm.display_name.trim() || null,
      });
      setConnectOpen(false);
      setMessage('WhatsApp number connected.');
      await fetchAccounts();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to connect.');
    } finally {
      setConnecting(false);
    }
  };

  const openConversation = useCallback(async (preview: WhatsAppConversationPreviewDTO) => {
    try {
      const token = await getToken();
      const res = await getWhatsAppConversation(token, preview.id);
      setConversation(res.conversation);
      setMessages(res.messages);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to open conversation.');
    }
  }, [getToken]);

  const handleManualReply = async () => {
    if (!conversation || !manualReply.trim()) return;
    setIsSending(true);
    setError(null);
    try {
      const token = await getToken();
      await replyToWhatsAppConversation(token, conversation.id, manualReply);
      const res = await getWhatsAppConversation(token, conversation.id);
      setMessages(res.messages);
      setManualReply('');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to send reply.');
    } finally {
      setIsSending(false);
    }
  };

  const handleStop = async () => {
    if (!conversation) return;
    try {
      const token = await getToken();
      await stopWhatsAppAgent(token, conversation.id);
      setConversation({ ...conversation, ai_agent_active: false });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to stop agent.');
    }
  };

  const handleResume = async () => {
    if (!conversation) return;
    try {
      const token = await getToken();
      await resumeWhatsAppAgent(token, conversation.id);
      setConversation({ ...conversation, ai_agent_active: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to resume agent.');
    }
  };

  const handleBookMeeting = async () => {
    if (!selectedAccount || !bookingForm.name.trim() || !bookingForm.date || !bookingForm.time) return;
    setIsSending(true);
    setError(null);
    try {
      const token = await getToken();
      await bookWhatsAppMeeting(token, {
        whatsapp_account_id: selectedAccount.id,
        conversation_id: conversation?.id || null,
        lead_name: bookingForm.name.trim(),
        lead_phone: conversation?.customer_phone || '',
        lead_company: '',
        meeting_datetime: `${bookingForm.date}T${bookingForm.time}`,
      });
      setBookingOpen(false);
      setMessage('Meeting booked! Lead added to CRM.');
      const cid = conversation?.id;
      if (cid) {
        const res = await getWhatsAppConversation(token, cid);
        setMessages(res.messages);
      }
      void fetchQuotaAndStats();
      void fetchPreviews();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to book meeting.');
    } finally {
      setIsSending(false);
    }
  };

  const handleExportCsv = async () => {
    try {
      const token = await getToken();
      const blob = await downloadWhatsAppBookedLeadsCsv(token);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'whatsapp-booked-leads.csv';
      a.click();
      window.URL.revokeObjectURL(url);
    } catch {
      /* ignore */
    }
  };

  const handleSyncTemplates = async () => {
    try {
      const token = await getToken();
      const res = await syncWhatsAppTemplates(token);
      setTemplates(res);
      setMessage('Template statuses synced from Meta.');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to sync templates.');
    }
  };

  const handleGenerateOutreach = async () => {
    if (selectedLeads.size === 0) return;
    setGenerating(true);
    setError(null);
    setMessage(null);
    try {
      const token = await getToken();
      const res = await generateWhatsAppOutreach(token, Array.from(selectedLeads));
      setDrafts(res);
      setDraftIdx(0);
      setEditingDraft(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to generate outreach.');
    } finally {
      setGenerating(false);
    }
  };

  const handleRegenerate = async () => {
    const draft = drafts[draftIdx];
    if (!draft) return;
    setRegenerating(true);
    setError(null);
    try {
      const token = await getToken();
      const res = await regenerateWhatsAppOutreach(token, draft.lead_id);
      setDrafts((prev) => prev.map((d, i) => (i === draftIdx ? res : d)));
      setEditingDraft(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to regenerate.');
    } finally {
      setRegenerating(false);
    }
  };

  const handleApproveOutreach = async () => {
    if (drafts.length === 0) return;
    setApproving(true);
    setError(null);
    try {
      const token = await getToken();
      const res = await approveWhatsAppOutreach(
        token,
        drafts.map((d) => ({ lead_id: d.lead_id, body: d.body })),
      );
      setMessage(`Sent: ${res.sent}, awaiting Meta approval: ${res.pending}, rejected: ${res.rejected}.`);
      setConfirmSend(false);
      void fetchOutreach();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to send outreach.');
    } finally {
      setApproving(false);
    }
  };

  const toggleLead = (id: string) => {
    setSelectedLeads((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const filteredPreviews = useMemo(() => {
    if (!search) return previews;
    const q = search.toLowerCase();
    return previews.filter(
      (p) =>
        (p.customer_name || p.customer_phone || '').toLowerCase().includes(q) ||
        (p.last_message || '').toLowerCase().includes(q)
    );
  }, [previews, search]);

  if (profileLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2Icon className="h-6 w-6 animate-spin text-chalk-faint" />
      </div>
    );
  }

  if (!profile || showSetup) {
    return (
      <div className="relative mx-auto w-full max-w-[900px] px-4 py-6">
        <div className="mb-5 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Link to={backTo} className="flex items-center gap-1.5 rounded-lg border border-ink-700 bg-ink-850 px-2.5 py-1.5 text-[12px] text-chalk-faint hover:border-ink-600 hover:text-chalk">
              <ArrowLeftIcon className="h-3.5 w-3.5" /> Back
            </Link>
            <span className="font-mono text-[11px] uppercase tracking-[0.16em] text-signal">Crawlio WhatsApp</span>
          </div>
          {profile && (
            <button onClick={() => setShowSetup(false)} className="flex h-8 items-center gap-1.5 rounded-lg border border-ink-700 bg-ink-850 px-3 text-[12px] text-chalk-dim hover:border-ink-600 hover:text-chalk">
              <XIcon className="h-3.5 w-3.5" /> Cancel
            </button>
          )}
        </div>
        <BusinessOnboarding initial={showSetup && profile ? profile : null} onComplete={(p) => { setProfile(p); setShowSetup(false); }} />
      </div>
    );
  }

  return (
    <div className="relative mx-auto w-full max-w-[1460px] min-h-screen">
      <div className="px-4 py-4">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Link to={backTo} className="flex items-center gap-1.5 rounded-lg border border-ink-700 bg-ink-850 px-2.5 py-1.5 text-[12px] text-chalk-faint hover:border-ink-600 hover:text-chalk">
              <ArrowLeftIcon className="h-3.5 w-3.5" /> Back
            </Link>
            <span className="font-mono text-[11px] uppercase tracking-[0.16em] text-signal">Crawlio WhatsApp</span>
          </div>
          <div className="flex items-center gap-2">
            {accounts.map((account) => (
              <button
                key={account.id}
                onClick={() => { setSelectedAccount(account); setPreviewPage(1); setConversation(null); setMessages([]); }}
                className={cn(
                  'flex h-7 items-center gap-1.5 rounded-lg border px-2.5 text-[11px]',
                  selectedAccount?.id === account.id
                    ? 'border-signal/50 bg-signal/10 text-signal'
                    : 'border-ink-700 bg-ink-850 text-chalk-dim hover:border-ink-600'
                )}
              >
                💬 {account.display_name || account.business_phone || account.phone_number_id}
              </button>
            ))}
            <button onClick={() => void openConnect()} className="flex h-7 items-center gap-1 rounded-lg border border-ink-700 bg-ink-850 px-2 text-[11px] text-chalk-dim hover:border-ink-600">
              <PlusIcon className="h-3 w-3" /> Connect
            </button>
          </div>
        </div>

        {error && <div className="mb-3 rounded-lg border border-ember/40 bg-ember/10 px-3 py-2 text-[12px] text-ember">{error}</div>}
        {message && <div className="mb-3 rounded-lg border border-signal/40 bg-signal/10 px-3 py-2 text-[12px] text-signal">{message}</div>}

        {loadingAccounts ? (
          <div className="flex h-[60vh] items-center justify-center">
            <Loader2Icon className="h-5 w-5 animate-spin text-chalk-faint" />
          </div>
        ) : accounts.length === 0 ? (
          <div className="mx-auto max-w-[480px] rounded-2xl border border-ink-800 bg-ink-900 p-6 text-center">
            <MessageCircleIcon className="mx-auto h-10 w-10 text-ink-700" />
            <h3 className="mt-3 text-[15px] font-semibold text-chalk">Connect a WhatsApp number</h3>
            <p className="mt-1 text-[12px] text-chalk-dim">
              Link your WhatsApp Business number and Crawlio will auto-reply to inbound messages, remember customer info,
              and book meetings into your CRM.
            </p>
            <button
              onClick={() => void openConnect()}
              className="mt-4 flex h-9 items-center gap-1.5 rounded-lg border border-signal/50 bg-signal/10 px-4 text-[12px] text-signal hover:bg-signal/20"
            >
              <PlusIcon className="h-4 w-4" /> Connect WhatsApp
            </button>
          </div>
        ) : (
          <>
            <div className="mb-3 flex flex-wrap items-center gap-1">
              {[
                { id: 'inbox' as const, label: 'Inbox', icon: InboxIcon },
                { id: 'outreach' as const, label: 'Outreach', icon: SparklesIcon },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setPageTab(tab.id)}
                  className={cn(
                    'flex h-8 items-center gap-1.5 rounded-lg border px-3 text-[12px] font-medium',
                    pageTab === tab.id
                      ? 'border-signal/50 bg-signal/10 text-signal'
                      : 'border-ink-700 bg-ink-850 text-chalk-dim hover:border-ink-600 hover:text-chalk'
                  )}
                >
                  <tab.icon className="h-3.5 w-3.5" /> {tab.label}
                </button>
              ))}
              <span className="mx-1 h-4 w-px bg-ink-800" />
              <button
                onClick={() => setShowSetup(true)}
                className="flex h-8 items-center gap-1.5 rounded-lg border border-ink-700 bg-ink-850 px-3 text-[12px] text-chalk-dim hover:border-ink-600 hover:text-chalk"
              >
                <SparklesIcon className="h-3.5 w-3.5" /> Business Info
              </button>
              <button onClick={handleExportCsv} className="flex h-8 items-center gap-1.5 rounded-lg border border-ink-700 bg-ink-850 px-3 text-[12px] text-chalk-dim hover:border-ink-600 hover:text-chalk">
                <DownloadIcon className="h-3.5 w-3.5" /> CSV
              </button>
            </div>

            {pageTab === 'inbox' ? (
              <div className="grid grid-cols-[248px_1fr_1.15fr] gap-3" style={{ height: 'calc(100vh - 84px)' }}>
                {/* Sidebar */}
                <aside className="flex flex-col gap-3 overflow-y-auto rounded-2xl border border-ink-800 bg-ink-900/80 p-3">
                  <div className="rounded-lg border border-ink-800 bg-ink-900 p-2.5">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-medium text-chalk-dim">Daily Quota</span>
                      <span className="text-[11px] font-mono text-signal">{quota ? `${quota.sent_count}/${quota.limit}` : '—'}</span>
                    </div>
                    <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-ink-800">
                      <div className="h-full rounded-full bg-signal" style={{ width: quota ? `${Math.min(100, (quota.sent_count / quota.limit) * 100)}%` : '0%' }} />
                    </div>
                  </div>

                  {stats && (
                    <div className="grid grid-cols-2 gap-1.5">
                      <div className="rounded-lg border border-ink-800 bg-ink-900 p-2">
                        <p className="font-mono text-[15px] text-chalk">{stats.inbound_received_today}</p>
                        <p className="text-[9px] text-chalk-dim">Inbound (today)</p>
                      </div>
                      <div className="rounded-lg border border-ink-800 bg-ink-900 p-2">
                        <p className="font-mono text-[15px] text-chalk">{stats.ai_replies_today}</p>
                        <p className="text-[9px] text-chalk-dim">AI Replies (today)</p>
                      </div>
                      <div className="rounded-lg border border-ink-800 bg-ink-900 p-2">
                        <p className="font-mono text-[15px] text-chalk">{stats.meetings_booked_today}</p>
                        <p className="text-[9px] text-chalk-dim">Booked (today)</p>
                      </div>
                      <div className="rounded-lg border border-ink-800 bg-ink-900 p-2">
                        <p className="font-mono text-[15px] text-chalk">{stats.active_conversations}</p>
                        <p className="text-[9px] text-chalk-dim">AI Active</p>
                      </div>
                    </div>
                  )}

                  <div className="flex items-center gap-1 rounded-lg border border-ink-700 bg-ink-850 px-2">
                    <SearchIcon className="h-3.5 w-3.5 text-chalk-dim" />
                    <input
                      type="text"
                      placeholder="Search..."
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      className="h-7 w-full border-0 bg-transparent text-[12px] text-chalk placeholder:text-chalk-dim focus:outline-none"
                    />
                  </div>

                  <div className="min-h-0 flex-1 overflow-y-auto">
                    {filteredPreviews.length === 0 && !loadingInbox ? (
                      <p className="py-8 text-center text-[11px] text-chalk-faint">No conversations yet — new WhatsApp replies appear here and are answered automatically.</p>
                    ) : (
                      <div className="divide-y divide-ink-800/70">
                        {filteredPreviews.map((p) => {
                          const name = p.customer_name || p.customer_phone || 'Unknown customer';
                          const initial = (name.charAt(0) || 'C').toUpperCase();
                          return (
                            <div
                              key={p.id}
                              className={cn(
                                'flex cursor-pointer items-center gap-3 px-2 py-2',
                                conversation?.id === p.id ? 'bg-ink-850' : 'hover:bg-ink-850/60'
                              )}
                              onClick={() => void openConversation(p)}
                            >
                              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-ink-800 text-[10px] font-semibold text-chalk-dim">{initial}</span>
                              <div className="min-w-0 flex-1">
                                <div className="flex items-center justify-between gap-2">
                                  <p className="truncate text-[12px] font-medium text-chalk">{name}</p>
                                  <span className="whitespace-nowrap text-[10px] text-chalk-faint">{p.last_message_at ? khiTime(p.last_message_at) : ''}</span>
                                </div>
                                <p className="truncate text-[11px] text-chalk-dim">{p.last_message || 'No message yet...'}</p>
                              </div>
                              {p.ai_agent_active && (
                                <span className="shrink-0 rounded-full border border-signal/30 bg-signal/10 px-1.5 py-0.25 text-[8px] text-signal">AI</span>
                              )}
                              {p.is_booked && (
                                <span className="shrink-0 rounded-full border border-amber/40 bg-amber/10 px-1.5 py-0.25 text-[8px] text-amber">Booked</span>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>

                  <footer className="flex items-center justify-between gap-2 border-t border-ink-850 pt-1.5">
                    <button onClick={() => setPreviewPage((p) => Math.max(1, p - 1))} disabled={previewPage <= 1} className="flex h-6 items-center gap-1 rounded border border-ink-700 bg-ink-850 px-2 text-[10px] text-chalk-dim hover:border-ink-600 disabled:opacity-40">
                      <ArrowLeftIcon className="h-3 w-3" /> Prev
                    </button>
                    <span className="text-[10px] text-chalk-faint">Page {previewPage}</span>
                    <button onClick={() => setPreviewPage((p) => p + 1)} disabled={!hasMore} className="flex h-6 items-center gap-1 rounded border border-ink-700 bg-ink-850 px-2 text-[10px] text-chalk-dim hover:border-ink-600 disabled:opacity-40">
                      Next <ArrowLeftIcon className="h-3 w-3 rotate-180" />
                    </button>
                  </footer>
                </aside>

                {/* Chat pane */}
                <section className="flex min-h-0 flex-col overflow-hidden rounded-2xl border border-ink-800 bg-ink-900">
                  {!conversation ? (
                    <div className="flex flex-1 items-center justify-center">
                      <div className="text-center">
                        <MessageCircleIcon className="mx-auto h-9 w-9 text-ink-700" />
                        <p className="mt-2 text-[12px] text-chalk-dim">Select a conversation or wait for the next inbound message</p>
                      </div>
                    </div>
                  ) : (
                    <>
                      <header className="flex items-start justify-between gap-2 border-b border-ink-850 px-4 py-3">
                        <div className="min-w-0 flex-1">
                          <h3 className="truncate text-[14px] font-semibold text-chalk">
                            {conversation.customer_name || conversation.customer_phone || 'Unknown'}
                          </h3>
                          <p className="mt-0.5 text-[11px] text-chalk-dim">{conversation.customer_phone}</p>
                        </div>
                        <button onClick={() => { setConversation(null); setMessages([]); }} className="rounded-lg p-1 text-chalk-faint hover:bg-ink-850 hover:text-chalk">
                          <XIcon className="h-4 w-4" />
                        </button>
                      </header>

                      <div className="flex items-center justify-between rounded-lg border border-ink-800 bg-ink-850 px-2.5 py-1.5">
                        <span className="flex items-center gap-1.5 text-[11px] text-chalk">
                          <span className={cn('h-1.5 w-1.5 rounded-full', conversation.ai_agent_active ? 'bg-signal animate-pulse' : 'bg-ink-600')} />
                          {profile?.business_name || 'AI'} Receptionist — {conversation.ai_agent_active ? 'Active' : 'Paused'}
                        </span>
                        <div className="flex gap-1">
                          <button
                            onClick={() => document.getElementById('wa-manual-reply-input')?.focus()}
                            className="flex h-6 items-center gap-1 rounded border border-ink-700 bg-ink-900 px-1.5 text-[10px] text-chalk hover:border-ink-600"
                          >
                            <MessageCircleIcon className="h-3 w-3" /> Reply
                          </button>
                          {conversation.ai_agent_active ? (
                            <button onClick={() => void handleStop()} className="flex h-6 items-center gap-1 rounded border border-ink-700 bg-ink-900 px-1.5 text-[10px] text-chalk-dim hover:border-ink-600">
                              <StopCircleIcon className="h-3 w-3" /> Stop Crawlio
                            </button>
                          ) : (
                            <button onClick={() => void handleResume()} className="flex h-6 items-center gap-1 rounded border border-signal/50 bg-signal/10 px-1.5 text-[10px] text-signal hover:bg-signal/20">
                              <PlayIcon className="h-3 w-3" /> Resume
                            </button>
                          )}
                        </div>
                      </div>

                      <div ref={setChatScrollRef} className="min-h-0 flex-1 space-y-2 overflow-y-auto px-4 py-3">
                        {messages.length === 0 ? (
                          <p className="py-8 text-center text-[11px] text-chalk-faint">No messages yet — the AI agent replies to the customer here.</p>
                        ) : (
                          messages.map((msg) => {
                            const isOutgoing = msg.sender_type === 'user' || msg.sender_type === 'ai';
                            const isSystem = msg.sender_type === 'system';
                            const label = isSystem ? 'System' : msg.sender_type === 'customer' ? (conversation.customer_name || conversation.customer_phone || 'Customer') : msg.sender_type === 'ai' ? 'AI Agent' : 'You';
                            const initial = (label.charAt(0) || '?').toUpperCase();
                            const time = msg.created_at ? khiTime(msg.created_at) : '';
                            return (
                              <div key={msg.id} className={cn('flex items-end gap-1.5', isSystem ? 'justify-center' : isOutgoing ? 'justify-end' : 'justify-start')}>
                                {!isSystem && !isOutgoing && <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-ink-800 text-[9px] font-semibold text-chalk-dim">{initial}</div>}
                                <div className={cn('max-w-[82%]', isSystem && 'mx-auto')}>
                                  {!isSystem && <div className={cn('mb-0.5 text-[9px] text-chalk-faint', isOutgoing ? 'text-right' : 'text-left')}>{label}</div>}
                                  <div className={cn(
                                    'whitespace-pre-wrap break-words px-2.5 py-1.5 text-[11px]',
                                    isSystem
                                      ? 'rounded-full bg-amber/10 text-center text-amber/90'
                                      : isOutgoing
                                      ? 'rounded-2xl rounded-br-sm bg-signal/15 text-chalk'
                                      : 'rounded-2xl rounded-bl-sm bg-ink-850 text-chalk'
                                  )}>
                                    {msg.content}
                                    {!isSystem && <span className={cn('mt-0.5 block text-right text-[8px] leading-none text-chalk-faint/80')}>{time}</span>}
                                  </div>
                                </div>
                                {!isSystem && isOutgoing && <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-signal/20 text-[9px] font-semibold text-signal">{initial}</div>}
                              </div>
                            );
                          })
                        )}
                      </div>

                      <div className="flex items-end gap-1 border-t border-ink-850 p-2.5">
                        <textarea
                          id="wa-manual-reply-input"
                          value={manualReply}
                          onChange={(e) => setManualReply(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' && !e.shiftKey) {
                              e.preventDefault();
                              if (manualReply.trim() && !isSending) void handleManualReply();
                            }
                          }}
                          placeholder="Type a message..."
                          rows={1}
                          className="min-h-[36px] max-h-24 flex-1 resize-none rounded-2xl rounded-br-sm border border-ink-700 bg-ink-900 px-3 py-2 text-[12px] text-chalk placeholder:text-chalk-faint focus:border-signal focus:outline-none"
                        />
                        <button onClick={() => setBookingOpen(true)} className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-amber/40 bg-amber/10 text-amber hover:bg-amber/20">
                          <CalendarIcon className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => void handleManualReply()}
                          disabled={isSending || !manualReply.trim()}
                          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-signal/50 bg-signal/10 text-signal hover:bg-signal/20 disabled:opacity-50"
                        >
                          {isSending ? <Loader2Icon className="h-4 w-4 animate-spin" /> : <SendIcon className="h-4 w-4" />}
                        </button>
                      </div>
                    </>
                  )}
                </section>

                {/* Activity panel */}
                <div className="min-h-0 overflow-hidden rounded-2xl border border-ink-800 bg-ink-900">
                  <ActivityPanel />
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-[248px_1fr] gap-3" style={{ height: 'calc(100vh - 84px)' }}>
                <ActivityPanel />
                <div className="min-h-0 overflow-hidden rounded-2xl border border-ink-800 bg-ink-900">
                  <div className="space-y-4 p-4">
                    {/* Usage */}
                    <div className="flex flex-wrap items-center gap-3">
                      <div className="rounded-lg border border-ink-800 bg-ink-900 px-3 py-2">
                        <span className="text-[10px] text-chalk-dim">Daily WhatsApp outreach</span>
                        <p className="font-mono text-[15px] text-chalk">{usage ? `${usage.used}/${usage.limit}` : '—'}</p>
                      </div>
                      <button onClick={handleSyncTemplates} className="flex h-8 items-center gap-1.5 rounded-lg border border-ink-700 bg-ink-850 px-3 text-[11px] text-chalk-dim hover:border-ink-600 hover:text-chalk">
                        <ArrowLeftIcon className="h-3 w-3 rotate-0" /> Sync template statuses
                      </button>
                    </div>

                    {/* Templates */}
                    {templates.length > 0 && (
                      <div>
                        <p className="mb-1.5 text-[11px] font-medium text-chalk-dim">Message Templates</p>
                        <div className="space-y-1.5">
                          {templates.map((t) => (
                            <div key={t.id} className="flex items-center justify-between gap-2 rounded-lg border border-ink-800 bg-ink-850 p-2">
                              <div className="min-w-0">
                                <p className="truncate font-mono text-[11px] text-chalk">{t.template_name}</p>
                                <p className="truncate text-[10px] text-chalk-faint">{t.body}</p>
                              </div>
                              <span className={cn(
                                'shrink-0 rounded-full border px-2 py-0.5 text-[9px]',
                                t.status === 'approved' ? 'border-emerald/40 bg-emerald/10 text-emerald'
                                  : t.status === 'rejected' ? 'border-ember/40 bg-ember/10 text-ember'
                                  : 'border-amber/40 bg-amber/10 text-amber'
                              )}>
                                {t.status}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {drafts.length === 0 ? (
                      <>
                        <p className="text-[12px] text-chalk">Select leads to draft AI outreach messages:</p>
                        {outreachLeads.length === 0 ? (
                          <p className="py-6 text-center text-[11px] text-chalk-faint">
                            No eligible leads — add leads with phone numbers first, or clear today's outreach.
                          </p>
                        ) : (
                          <div className="space-y-1.5">
                            {outreachLeads.map((lead) => (
                              <label key={lead.lead_id} className="flex cursor-pointer items-center gap-2 rounded-lg border border-ink-800 bg-ink-850 px-2.5 py-2 hover:border-ink-600">
                                <input
                                  type="checkbox"
                                  checked={selectedLeads.has(lead.lead_id)}
                                  onChange={() => toggleLead(lead.lead_id)}
                                  className="accent-signal"
                                />
                                <div className="min-w-0 flex-1">
                                  <p className="truncate text-[12px] font-medium text-chalk">{lead.name}</p>
                                  <p className="truncate text-[10px] text-chalk-faint">{lead.phone} · {lead.company || 'no company'}</p>
                                </div>
                              </label>
                            ))}
                          </div>
                        )}
                        <button
                          onClick={() => void handleGenerateOutreach()}
                          disabled={selectedLeads.size === 0 || generating}
                          className="flex h-8 items-center gap-1.5 rounded-lg border border-signal/50 bg-signal/10 px-3 text-[11px] text-signal hover:bg-signal/20 disabled:opacity-50"
                        >
                          {generating ? <Loader2Icon className="h-3.5 w-3.5 animate-spin" /> : <SparklesIcon className="h-3.5 w-3.5" />}
                          Generate drafts ({selectedLeads.size})
                        </button>
                      </>
                    ) : (
                      <div className="space-y-3">
                        <div className="flex flex-wrap items-center gap-1.5">
                          {drafts.map((d, i) => (
                            <button
                              key={d.lead_id}
                              onClick={() => { setDraftIdx(i); setEditingDraft(false); }}
                              className={cn(
                                'flex h-7 items-center gap-1 rounded-lg border px-2.5 text-[11px]',
                                i === draftIdx ? 'border-signal/50 bg-signal/10 text-signal' : 'border-ink-700 bg-ink-850 text-chalk-dim hover:border-ink-600'
                              )}
                            >
                              {d.recipient_name || d.recipient_phone}
                            </button>
                          ))}
                        </div>

                        {drafts[draftIdx] && (
                          <div className="rounded-xl border border-ink-800 bg-ink-900 p-3">
                            <div className="flex items-start justify-between gap-2">
                              <div>
                                <p className="text-[12px] font-medium text-chalk">{drafts[draftIdx].recipient_name || drafts[draftIdx].recipient_phone}</p>
                                <p className="text-[10px] text-chalk-faint">{drafts[draftIdx].recipient_phone} · {drafts[draftIdx].recipient_company || 'no company'}</p>
                              </div>
                              <div className="flex gap-1">
                                <button onClick={() => setEditingDraft(true)} disabled={regenerating} className="flex h-6 items-center gap-1 rounded border border-ink-700 bg-ink-850 px-1.5 text-[10px] text-chalk hover:border-ink-600">
                                  <EditIcon className="h-3 w-3" /> Edit
                                </button>
                                <button onClick={() => void handleRegenerate()} disabled={regenerating} className="flex h-6 items-center gap-1 rounded border border-ink-700 bg-ink-850 px-1.5 text-[10px] text-chalk hover:border-ink-600">
                                  {regenerating ? <Loader2Icon className="h-3 w-3 animate-spin" /> : <SparklesIcon className="h-3 w-3" />} Regenerate
                                </button>
                              </div>
                            </div>
                            {editingDraft ? (
                              <textarea
                                value={drafts[draftIdx].body}
                                onChange={(e) => setDrafts((prev) => prev.map((d, i) => (i === draftIdx ? { ...d, body: e.target.value } : d)))}
                                rows={4}
                                className="mt-2 w-full rounded-lg border border-ink-700 bg-ink-950 px-2.5 py-1.5 text-[12px] text-chalk focus:border-signal focus:outline-none"
                              />
                            ) : (
                              <p className="mt-2 whitespace-pre-wrap rounded-lg border border-ink-800 bg-ink-950 p-2.5 text-[12px] text-chalk-dim">{drafts[draftIdx].body}</p>
                            )}
                          </div>
                        )}

                        <div className="flex items-center gap-2">
                          {!confirmSend ? (
                            <button onClick={() => setConfirmSend(true)} disabled={approving} className="flex h-8 items-center gap-1.5 rounded-lg border border-signal/50 bg-signal/10 px-3 text-[11px] text-signal hover:bg-signal/20">
                              <SendIcon className="h-3.5 w-3.5" /> Approve & Send ({drafts.length})
                            </button>
                          ) : (
                            <>
                              <button onClick={() => void handleApproveOutreach()} disabled={approving} className="flex h-8 items-center gap-1.5 rounded-lg border border-signal/50 bg-signal/10 px-3 text-[11px] text-signal hover:bg-signal/20">
                                {approving ? <Loader2Icon className="h-3.5 w-3.5 animate-spin" /> : <CheckIcon className="h-3.5 w-3.5" />} Confirm send
                              </button>
                              <button onClick={() => setConfirmSend(false)} className="flex h-8 items-center gap-1.5 rounded-lg border border-ink-700 bg-ink-850 px-3 text-[11px] text-chalk-dim hover:border-ink-600">
                                <XIcon className="h-3.5 w-3.5" /> Cancel
                              </button>
                            </>
                          )}
                        </div>
                        <p className="text-[10px] text-chalk-faint">
                          Outreach uses Meta-approved message templates. If a template is new it first goes to Meta for review,
                          then sends automatically once approved — hit "Sync template statuses" to refresh.
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </>
        )}

        {/* Connect dialog */}
        {connectOpen && (
          <div className="fixed inset-0 z-[80] flex items-end justify-center p-0 sm:items-center sm:p-6">
            <div className="absolute inset-0 bg-ink-950/90 backdrop-blur-sm" onClick={() => setConnectOpen(false)} />
            <div className="relative flex max-h-[88vh] w-full max-w-[520px] flex-col overflow-hidden rounded-t-2xl border border-ink-700 bg-ink-900 sm:rounded-2xl">
              <div className="flex items-start justify-between gap-4 border-b border-ink-850 px-6 py-5">
                <div>
                  <h2 className="font-display text-[18px] font-semibold tracking-tight text-chalk">Connect WhatsApp</h2>
                  <p className="mt-1 text-[12px] text-chalk-faint">
                    {testMode ? 'Manual credentials (System User token)' : 'Meta Embedded Signup'}
                  </p>
                </div>
                <button onClick={() => setConnectOpen(false)} className="rounded-lg p-1.5 text-chalk-faint hover:bg-ink-850 hover:text-chalk">
                  <XIcon className="h-4 w-4" />
                </button>
              </div>
              <div className="overflow-y-auto p-6">
                {!testMode && authUrl ? (
                  <div className="space-y-3">
                    <p className="text-[12px] text-chalk-dim">
                      Click below to authorize Crawlio through Meta's secure Embedded Signup. You'll be connected to the first
                      WhatsApp number on your business.
                    </p>
                    <button
                      onClick={handleEmbeddedConnect}
                      className="flex h-9 w-full items-center justify-center gap-1.5 rounded-lg border border-signal/50 bg-signal/10 text-[12px] text-signal hover:bg-signal/20"
                    >
                      <PlusIcon className="h-4 w-4" /> Continue with Meta
                    </button>
                  </div>
                ) : (
                  <div className="space-y-2.5">
                    <p className="text-[12px] text-chalk-dim">
                      Add your number's <span className="text-chalk">Phone Number ID</span> and a permanent
                      <span className="text-chalk"> System User token</span> (Meta app → WhatsApp → API Setup). The token is
                      checked against the Graph API before saving.
                    </p>
                    <input
                      value={manualForm.phone_number_id}
                      onChange={(e) => setManualForm((f) => ({ ...f, phone_number_id: e.target.value }))}
                      placeholder="Phone Number ID"
                      className="h-9 w-full rounded-lg border border-ink-700 bg-ink-950 px-3 text-[12px] text-chalk placeholder:text-chalk-dim focus:border-signal focus:outline-none"
                    />
                    <input
                      value={manualForm.access_token}
                      onChange={(e) => setManualForm((f) => ({ ...f, access_token: e.target.value }))}
                      placeholder="System User Access Token"
                      type="password"
                      className="h-9 w-full rounded-lg border border-ink-700 bg-ink-950 px-3 text-[12px] text-chalk placeholder:text-chalk-dim focus:border-signal focus:outline-none"
                    />
                    <input
                      value={manualForm.waba_id}
                      onChange={(e) => setManualForm((f) => ({ ...f, waba_id: e.target.value }))}
                      placeholder="WABA ID (optional)"
                      className="h-9 w-full rounded-lg border border-ink-700 bg-ink-950 px-3 text-[12px] text-chalk placeholder:text-chalk-dim focus:border-signal focus:outline-none"
                    />
                    <input
                      value={manualForm.business_phone}
                      onChange={(e) => setManualForm((f) => ({ ...f, business_phone: e.target.value }))}
                      placeholder="Business phone e.g. +1 555 000 0000 (optional)"
                      className="h-9 w-full rounded-lg border border-ink-700 bg-ink-950 px-3 text-[12px] text-chalk placeholder:text-chalk-dim focus:border-signal focus:outline-none"
                    />
                    <input
                      value={manualForm.display_name}
                      onChange={(e) => setManualForm((f) => ({ ...f, display_name: e.target.value }))}
                      placeholder="Display name (optional)"
                      className="h-9 w-full rounded-lg border border-ink-700 bg-ink-950 px-3 text-[12px] text-chalk placeholder:text-chalk-dim focus:border-signal focus:outline-none"
                    />
                    <button
                      onClick={() => void handleManualConnect()}
                      disabled={connecting}
                      className="flex h-9 w-full items-center justify-center gap-1.5 rounded-lg border border-signal/50 bg-signal/10 text-[12px] text-signal hover:bg-signal/20 disabled:opacity-50"
                    >
                      {connecting ? <Loader2Icon className="h-4 w-4 animate-spin" /> : <CheckIcon className="h-4 w-4" />}
                      Connect
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Booking dialog */}
        {bookingOpen && (
          <div className="fixed inset-0 z-[80] flex items-end justify-center p-0 sm:items-center sm:p-6">
            <div className="absolute inset-0 bg-ink-950/90 backdrop-blur-sm" onClick={() => setBookingOpen(false)} />
            <div className="relative w-full max-w-[440px] rounded-t-2xl border border-ink-700 bg-ink-900 p-6 sm:rounded-2xl">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="font-display text-[16px] font-semibold tracking-tight text-chalk">Book Meeting</h2>
                  <p className="mt-1 text-[12px] text-chalk-faint">Save this lead as a Hot lead + create the meeting.</p>
                </div>
                <button onClick={() => setBookingOpen(false)} className="rounded-lg p-1.5 text-chalk-faint hover:bg-ink-850 hover:text-chalk">
                  <XIcon className="h-4 w-4" />
                </button>
              </div>
              <div className="mt-4 space-y-2.5">
                <input
                  value={bookingForm.name}
                  onChange={(e) => setBookingForm((f) => ({ ...f, name: e.target.value }))}
                  placeholder="Lead name (defaults to customer)"
                  className="h-9 w-full rounded-lg border border-ink-700 bg-ink-950 px-3 text-[12px] text-chalk placeholder:text-chalk-dim focus:border-signal focus:outline-none"
                />
                <div className="grid grid-cols-2 gap-2">
                  <input
                    type="date"
                    value={bookingForm.date}
                    onChange={(e) => setBookingForm((f) => ({ ...f, date: e.target.value }))}
                    className="h-9 w-full rounded-lg border border-ink-700 bg-ink-950 px-3 text-[12px] text-chalk focus:border-signal focus:outline-none"
                  />
                  <input
                    type="time"
                    value={bookingForm.time}
                    onChange={(e) => setBookingForm((f) => ({ ...f, time: e.target.value }))}
                    className="h-9 w-full rounded-lg border border-ink-700 bg-ink-950 px-3 text-[12px] text-chalk focus:border-signal focus:outline-none"
                  />
                </div>
                <button
                  onClick={() => void handleBookMeeting()}
                  disabled={isSending || !bookingForm.date || !bookingForm.time}
                  className="flex h-9 w-full items-center justify-center gap-1.5 rounded-lg border border-signal/50 bg-signal/10 text-[12px] text-signal hover:bg-signal/20 disabled:opacity-50"
                >
                  {isSending ? <Loader2Icon className="h-4 w-4 animate-spin" /> : <CalendarIcon className="h-4 w-4" />}
                  Book Meeting
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}