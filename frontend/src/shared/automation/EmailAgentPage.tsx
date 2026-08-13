import React, { useCallback, useEffect, useMemo, useState, useRef } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '@clerk/clerk-react';
import {
  ArrowLeftIcon, MailIcon, PlusIcon, Loader2Icon, InboxIcon, SendIcon,
  TrashIcon, UserIcon, MessageCircleIcon, SparklesIcon,
  StopCircleIcon, PlayIcon, CheckIcon, CalendarIcon, DownloadIcon, XIcon,
  FileTextIcon, SearchIcon, ShieldAlertIcon
} from 'lucide-react';
import { cn } from '../utils/cn';
import { formatSender, getSenderFromEmail, parseSender } from '../utils/sender';
import { khiTime } from '../utils/time';
import {
  listEmailAccounts,
  getGoogleAuthUrl,
  getEmailQuota,
  type EmailAccountDTO,
  type EmailQuotaDTO,
  type EmailMessageDTO,
  type EmailMessageListResponseDTO,
  type EmailConversationDTO,
  type EmailConversationMessageDTO,
  type ConversationPreviewDTO,
  getConversationPreviews,
  startConversation,
  getConversation,
  sendManualReply,
  bookMeeting,
  saveBusinessInfo,
  stopConversation,
  resumeConversation,
  downloadBookedLeadsCsv,
  generateAIEmail,
  approveAIEmail,
  updateEmailDraft,
  type EmailDraftDTO,
  processInboundReplies,
} from '../../lib/api/emailAgent';
import { apiFetch, ApiError } from '../../lib/api/client';
import { getBusinessProfile, type BusinessProfileDTO } from '../../lib/api/agent';
import { ComposeDialog } from './ComposeDialog';
import { WriteWithCrawlioDialog } from './WriteWithCrawlioDialog';
import { EmailQuotaBar } from './EmailQuotaBar';
import { RAGAgentPanel } from './RAGAgentPanel';
import { BusinessOnboarding } from './BusinessOnboarding';
import { OutreachTab } from './OutreachTab';
import { CrmTab } from './CrmTab';
import { ActivityPanel } from './ActivityPanel';

type Step = 'conversation' | 'preview' | 'booking';

function htmlToPlainText(html: string): string {
  const tmp = document.createElement('div');
  tmp.innerHTML = html || '';
  const text = tmp.textContent || tmp.innerText || '';
  tmp.remove();
  return text.replace(/&nbsp;/g, ' ').replace(/[ \t]+/g, ' ').replace(/\n{3,}/g, '\n\n').trim();
}

interface Props {
  backTo: string;
}

export function EmailAgentPage({ backTo }: Props) {
  const { getToken } = useAuth();
  const [accounts, setAccounts] = useState<EmailAccountDTO[]>([]);
  const [selectedAccount, setSelectedAccount] = useState<EmailAccountDTO | null>(null);
  const [quota, setQuota] = useState<EmailQuotaDTO | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [composeOpen, setComposeOpen] = useState(false);
  const [writeAIOpen, setWriteAIOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<'inbox' | 'sent' | 'trash' | 'spam'>('inbox');
  const [emails, setEmails] = useState<EmailMessageDTO[]>([]);
  const [loadingEmails, setLoadingEmails] = useState(false);
  const [emailPage, setEmailPage] = useState(1);
  const [hasMoreEmails, setHasMoreEmails] = useState(false);
  const [inboxPreviews, setInboxPreviews] = useState<ConversationPreviewDTO[]>([]);
  const [selectedEmail, setSelectedEmail] = useState<EmailMessageDTO | null>(null);
  const [showAgent, setShowAgent] = useState(false);
  const [emailSearch, setEmailSearch] = useState('');
  const [inboundError, setInboundError] = useState<string | null>(null);

  // Workspace-wide agent setup (onboarding gate) + top-level views
  const [pageTab, setPageTab] = useState<'inbox' | 'outreach' | 'crm'>('inbox');
  const [profile, setProfile] = useState<BusinessProfileDTO | null>(null);
  const [profileLoading, setProfileLoading] = useState(true);
  const [showSetup, setShowSetup] = useState(false);

  // Conversation state
  const [conversation, setConversation] = useState<EmailConversationDTO | null>(null);
  const [messages, setMessages] = useState<EmailConversationMessageDTO[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [conversationStep, setConversationStep] = useState<Step>('conversation');
  const [previewDraft, setPreviewDraft] = useState<EmailDraftDTO | null>(null);
  const [previewEditing, setPreviewEditing] = useState(false);
  const [editSubject, setEditSubject] = useState('');
  const [editBody, setEditBody] = useState('');
  const [isSavingEdit, setIsSavingEdit] = useState(false);
  const [businessName, setBusinessName] = useState('');
  const [businessSubject, setBusinessSubject] = useState('');
  const [businessInfo, setBusinessInfo] = useState('');
  const [manualReply, setManualReply] = useState('');
  const [meetingName, setMeetingName] = useState('');
  const [meetingEmail, setMeetingEmail] = useState('');
  const [meetingCompany, setMeetingCompany] = useState('');
  const [meetingDate, setMeetingDate] = useState('');
  const [meetingTime, setMeetingTime] = useState('');

  // Booked meetings
  const [bookedLeads, setBookedLeads] = useState<EmailConversationDTO[]>([]);

  // Three.js ref
  const canvasRef = useRef<HTMLDivElement>(null);
  const chatScrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight;
    }
  }, [messages, conversationStep]);

  const fetchAccounts = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const token = await getToken();
      const res = await listEmailAccounts(token);
      setAccounts(res.items);
      if (res.items.length > 0 && !selectedAccount) {
        setSelectedAccount(res.items[0]);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load email accounts.');
    } finally {
      setIsLoading(false);
    }
  }, [getToken, selectedAccount]);

  const fetchQuota = useCallback(async () => {
    if (!selectedAccount) return;
    try {
      const token = await getToken();
      const res = await getEmailQuota(token, selectedAccount.id);
      setQuota(res);
    } catch (err) {
      console.error('Failed to load quota:', err);
    }
  }, [getToken, selectedAccount]);

  const fetchEmails = useCallback(async () => {
    if (!selectedAccount) return;
    setLoadingEmails(true);
    try {
      const token = await getToken();

      // Fire-and-forget: auto-respond to new customer replies in the background
      // so the inbox list renders immediately instead of blocking on Gmail + AI.
      if (activeTab === 'inbox') {
        processInboundReplies(token, selectedAccount.id)
          .then((res) => {
            if (res?.reconnect_required) {
              setInboundError('Gmail connection expired — please reconnect.');
            } else {
              setInboundError(null);
            }
          });
        const prev = await getConversationPreviews(token, selectedAccount.id, emailPage, 10);
        setInboxPreviews(prev.items);
        setHasMoreEmails(prev.has_more ?? false);
        setEmails([]);
      } else {
        const res = await apiFetch<EmailMessageListResponseDTO>(
          `/api/v1/email-accounts/${selectedAccount.id}/${activeTab}?page=${emailPage}&page_size=10`,
          token
        );
        setEmails(res.items);
        setHasMoreEmails(res.has_more ?? false);
        setInboxPreviews([]);
      }
    } catch (err) {
      console.error('Failed to load emails:', err);
    } finally {
      setLoadingEmails(false);
    }
  }, [getToken, selectedAccount, activeTab, emailPage]);

  const fetchEmailDetail = useCallback(
    async (emailId: string) => {
      if (!selectedAccount) return;
      try {
        const token = await getToken();
        const res = await apiFetch<EmailMessageDTO>(
          `/api/v1/email-accounts/${selectedAccount.id}/messages/${emailId}`,
          token
        );
        // Ensure from_email and body are properly set
        const emailWithBody: EmailMessageDTO = {
          id: res.id,
          thread_id: res.thread_id,
          subject: res.subject || '',
          from_email: res.from_email || '',
          to_email: res.to_email || '',
          date: res.date || '',
          body: res.body || res.snippet || 'No content available',
          body_preview: res.body_preview || res.snippet || '',
          snippet: res.snippet || '',
          label_ids: res.label_ids || [],
          is_read: res.is_read ?? true,
          is_customer_interested: res.is_customer_interested ?? false,
          has_conversation: res.has_conversation ?? false,
        };
        setSelectedEmail(emailWithBody);

        // Check if there's an existing conversation (match by customer email or thread)
        const convRes = await apiFetch<{ items: EmailConversationDTO[] }>(
          `/api/v1/email-conversations/accounts/${selectedAccount.id}/active`,
          token
        );
        const senderEmail = (getSenderFromEmail(emailWithBody)?.email || '').toLowerCase();
        const existing = convRes.items.find(
          (c) =>
            (senderEmail && c.customer_email && c.customer_email.toLowerCase() === senderEmail) ||
            (emailWithBody.thread_id && c.thread_id && c.thread_id === emailWithBody.thread_id)
        );
        if (existing) {
          const fullConv = await getConversation(token, existing.id);
          setConversation(existing);
          setMessages(fullConv.messages);
          setConversationStep('conversation');
        } else {
          resetConversation();
        }
      } catch (err) {
        console.error('Failed to load email:', err);
        setError(err instanceof ApiError ? err.message : 'Failed to load email.');
      }
    },
    [getToken, selectedAccount]
  );

  const fetchConversation = useCallback(async () => {
    if (!selectedEmail || !selectedAccount) return;
    try {
      const token = await getToken();
      const convRes = await apiFetch<{ items: EmailConversationDTO[] }>(
        `/api/v1/email-conversations/accounts/${selectedAccount.id}/active`,
        token
      );
      const senderEmail = (getSenderFromEmail(selectedEmail)?.email || '').toLowerCase();
      const existing = convRes.items.find(
        (c) =>
          (senderEmail && c.customer_email && c.customer_email.toLowerCase() === senderEmail) ||
          (selectedEmail.thread_id && c.thread_id && c.thread_id === selectedEmail.thread_id)
      );
      if (existing) {
        const fullConv = await getConversation(token, existing.id);
        setConversation(existing);
        setMessages(fullConv.messages);
        setConversationStep('conversation');
      } else {
        resetConversation();
      }
    } catch (err) {
      console.error('Failed to load conversation:', err);
      resetConversation();
    }
  }, [getToken, selectedEmail, selectedAccount]);

  useEffect(() => {
    void fetchAccounts();
  }, []);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const token = await getToken();
        const res = await getBusinessProfile(token);
        if (!cancelled) setProfile(res);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : 'Failed to load business profile.');
      } finally {
        if (!cancelled) setProfileLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [getToken]);

  useEffect(() => {
    void fetchQuota();
  }, [selectedAccount]);

  useEffect(() => {
    void fetchEmails();
  }, [selectedAccount, activeTab]);

  // Real-time inbox: poll for new inbound every 30s so the assistant
  // receives customer replies and replies back automatically without a manual click.
  useEffect(() => {
    if (!selectedAccount) return;
    const tick = () => {
      void getToken().then((token) => {
        processInboundReplies(token, selectedAccount.id)
          .then((res) => {
            if (res?.reconnect_required) {
              setInboundError('Gmail connection expired — please reconnect.');
            } else {
              setInboundError(null);
            }
          })
          .catch((err) => {
            const status = err instanceof ApiError ? err.status : 0;
            setInboundError(
              status === 401
                ? 'Gmail connection expired — please reconnect.'
                : `Could not sync inbox: ${err instanceof Error ? err.message : String(err)}`,
            );
          });
        void fetchEmails();
      });
    };
    tick(); // initial immediate sync
    const id = window.setInterval(tick, 30000);
    return () => clearInterval(id);
  }, [selectedAccount, fetchEmails, getToken]);

  const resetConversation = () => {
    setConversation(null);
    setMessages([]);
    setConversationStep('conversation');
    setPreviewDraft(null);
    setBusinessName('');
    setBusinessSubject('');
    setBusinessInfo('');
    setManualReply('');
    setIsGenerating(false);
    setIsSending(false);
  };

  const handleConnectGoogle = async () => {
    try {
      const token = await getToken();
      const res = await getGoogleAuthUrl(token);
      window.location.href = res.auth_url;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to connect Google.');
    }
  };

  const handleStartConversation = async () => {
    if (!selectedEmail || !selectedAccount) return;

    setIsGenerating(true);
    setError(null);

    try {
      const token = await getToken();
      const sender = selectedEmail ? getSenderFromEmail(selectedEmail) : null;
      const conv = await startConversation(token, {
        email_account_id: selectedAccount.id,
        email_id: selectedEmail.id,
        lead_name: sender?.name || '',
        lead_email: sender?.email || '',
        thread_id: selectedEmail.thread_id || null,
      });
      setConversation(conv);

      // Auto-fill business context from the saved business profile (no form needed).
      await saveBusinessInfo(token, selectedAccount.id, conv.id, {
        business_name: profile?.business_name || businessName,
        business_subject: profile?.services || businessSubject,
        business_additional_info: profile?.knowledge_base || businessInfo,
      });

      setConversationStep('conversation');
      const updatedConv = await getConversation(token, conv.id);
      setMessages(updatedConv.messages);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to start conversation.');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleManualReply = async () => {
    if (!conversation || !selectedAccount || !manualReply.trim()) return;

    setIsSending(true);
    setError(null);

    try {
      const token = await getToken();
      // Send reply email directly to the customer + log it in the conversation
      await sendManualReply(token, conversation.id, manualReply);

      const updated = await getConversation(token, conversation.id);
      setMessages(updated.messages);
      setManualReply('');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to send reply.');
    } finally {
      setIsSending(false);
    }
  };

  const handlePreviewOutreach = async () => {
    if (!conversation || !selectedAccount) return;

    setIsGenerating(true);
    setError(null);

    try {
      const token = await getToken();
      const businessCtx = conversation.business_context;
      let businessNameVal = profile?.business_name || businessName;
      let businessSubjectVal = profile?.services || businessSubject;
      let businessInfoVal = profile?.knowledge_base || businessInfo;

      if (businessCtx) {
        try {
          const ctx = JSON.parse(businessCtx);
          businessNameVal = ctx.business_name || businessName;
          businessSubjectVal = ctx.business_subject || businessSubject;
          businessInfoVal = ctx.business_additional_info || businessInfo;
        } catch (e) {
          businessInfoVal = businessCtx;
        }
      }

      const sender = selectedEmail ? getSenderFromEmail(selectedEmail) : null;
      const draft = await generateAIEmail(token, {
        email_account_id: selectedAccount.id,
        prompt: `Generate outreach email to ${sender?.email || sender?.name || ''}. Business: ${businessNameVal}. Subject: ${businessSubjectVal}. Additional: ${businessInfoVal}`,
        lead_name: sender?.name || '',
        lead_email: sender?.email || '',
      });
      setPreviewDraft(draft);
      setConversationStep('preview');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to generate preview.');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleApproveAndSend = async () => {
    if (!previewDraft) return;

    try {
      const token = await getToken();
      await approveAIEmail(token, previewDraft.id);
      setConversationStep('booking');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to send email.');
    }
  };

  const handleStartEditPreview = () => {
    if (!previewDraft) return;
    setEditSubject(previewDraft.subject);
    setEditBody(previewDraft.body);
    setPreviewEditing(true);
  };

  const handleSavePreview = async () => {
    if (!previewDraft) return;
    setIsSavingEdit(true);
    setError(null);
    try {
      const token = await getToken();
      const updated = await updateEmailDraft(token, previewDraft.id, {
        subject: editSubject,
        body: editBody,
      });
      setPreviewDraft(updated);
      setPreviewEditing(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to save edit.');
    } finally {
      setIsSavingEdit(false);
    }
  };

  const handleStop = async () => {
    if (!conversation) return;
    try {
      const token = await getToken();
      await stopConversation(token, conversation.id);
      setConversation({ ...conversation, ai_agent_active: false });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to stop agent.');
    }
  };

  const handleResume = async () => {
    if (!conversation) return;
    try {
      const token = await getToken();
      await resumeConversation(token, conversation.id);
      setConversation({ ...conversation, ai_agent_active: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to resume agent.');
    }
  };

  const handleBookMeeting = async (overrides?: { name?: string; email?: string; company?: string; date?: string; time?: string }) => {
    if (!conversation || !selectedAccount) return;
    try {
      const token = await getToken();
      const n = overrides?.name ?? meetingName;
      const e = overrides?.email ?? meetingEmail;
      const c = overrides?.company ?? meetingCompany;
      const d = overrides?.date ?? meetingDate;
      const t = overrides?.time ?? meetingTime;
      await bookMeeting(token, {
        email_account_id: selectedAccount.id,
        conversation_id: conversation.id,
        lead_name: n,
        lead_email: e,
        lead_company: c,
        meeting_datetime: `${d}T${t}`,
      });
      setConversationStep('booking');
      // Add to booked leads
      setBookedLeads((prev) => [...prev, conversation]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to book meeting.');
    }
  };

  const handleExportCsv = async () => {
    try {
      const token = await getToken();
      const blob = await downloadBookedLeadsCsv(token);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'booked_leads.csv';
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to export CSV:', err);
    }
  };

  const handleExportLeadToCrm = async (lead: EmailConversationDTO) => {
    try {
      const token = await getToken();
      if (!selectedAccount) return;

      // Get full conversation for export
      const conv = await getConversation(token, lead.id);

      // Export to CRM
      await apiFetch('/api/v1/crm/import-email-conversation', token, {
        method: 'POST',
        body: JSON.stringify({
          conversation_id: lead.id,
          lead_name: lead.lead_name || '',
          lead_email: lead.lead_email || '',
          subject: lead.subject || '',
          messages: conv.messages.map((m) => ({
            sender_type: m.sender_type,
            content: m.content,
            sent_at: m.sent_at,
          })),
        }),
      });

      alert('Lead exported to CRM successfully!');
    } catch (err) {
      console.error('Failed to export to CRM:', err);
      alert('Failed to export to CRM');
    }
  };

  const filteredEmails = useMemo(() => {
    if (!emailSearch) return emails;
    const q = emailSearch.toLowerCase();
    return emails.filter(
      (e) =>
        (e.subject || '').toLowerCase().includes(q) ||
        (e.from_email || '').toLowerCase().includes(q) ||
        (getSenderFromEmail(e)?.name || '').toLowerCase().includes(q) ||
        (getSenderFromEmail(e)?.email || '').toLowerCase().includes(q)
    );
  }, [emails, emailSearch]);

  const filteredPreviews = useMemo(() => {
    if (!emailSearch) return inboxPreviews;
    const q = emailSearch.toLowerCase();
    return inboxPreviews.filter(
      (p) =>
        (p.customer_name || p.customer_email || '').toLowerCase().includes(q) ||
        (p.last_message || '').toLowerCase().includes(q)
    );
  }, [inboxPreviews, emailSearch]);

  const openConversationFromPreview = useCallback(
    async (preview: ConversationPreviewDTO) => {
      if (!selectedAccount) return;
      try {
        const token = await getToken();
        const conv = await getConversation(token, preview.id);
        setConversation(conv.conversation);
        setMessages(conv.messages);
        setConversationStep('conversation');
        const customer = conv.conversation.customer_name || conv.conversation.customer_email || '';
        setSelectedEmail({
          id: conv.conversation.id,
          thread_id: (conv.conversation as any).thread_id ?? null,
          subject: customer ? `Conversation with ${customer}` : '(No subject)',
          from_email: conv.conversation.customer_email || '',
          to_email: '',
          date: preview.last_message_at || '',
          body: preview.last_message || '',
          body_preview: '',
          snippet: preview.last_message || '',
          label_ids: [],
          is_read: true,
          is_customer_interested: false,
          has_conversation: true,
        });
      } catch (err) {
        console.error('Failed to load conversation:', err);
        setError(err instanceof ApiError ? err.message : 'Failed to load conversation.');
      }
    },
    [getToken, selectedAccount],
  );

  const quotaPercent = quota ? Math.min(100, (quota.total_sent / quota.limit) * 100) : 0;

  // Simple Three.js background canvas
  useEffect(() => {
    if (!canvasRef.current) return;

    let scene: any;
    let camera: any;
    let renderer: any;
    let mesh: any;
    let group: any;
    let mouseX = 0;
    let mouseY = 0;
    let disposed = false;

    const init = async () => {
      const THREE = (await import('three')).default;

      scene = new THREE.Scene();
      camera = new THREE.PerspectiveCamera(75, 1, 0.1, 1000);

      renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
      renderer.setSize(canvasRef.current!.clientWidth, canvasRef.current!.clientHeight);
      renderer.setPixelRatio(window.devicePixelRatio);
      canvasRef.current!.appendChild(renderer.domElement);

      const geometry = new THREE.IcosahedronGeometry(0.5, 2, 0);
      const material = new THREE.MeshBasicMaterial({
        color: 0x6366f1,
        wireframe: true,
        opacity: 0.15,
        transparent: true,
      });

      group = new THREE.Group();
      for (let i = 0; i < 8; i++) {
        mesh = new THREE.Mesh(geometry, material);
        mesh.position.x = (Math.random() - 0.5) * 3;
        mesh.position.y = (Math.random() - 0.5) * 3;
        mesh.position.z = (Math.random() - 0.5) * 3;
        group.add(mesh);
      }
      scene.add(group);

      camera.position.z = 3;

      const animate = () => {
        if (disposed) return;
        requestAnimationFrame(animate);
        group.rotation.x = mouseY * 0.01;
        group.rotation.y = mouseX * 0.01;
        group.rotation.z += 0.001;
        renderer.render(scene, camera);
      };
      animate();

      const handleMouseMove = (e: MouseEvent) => {
        mouseX = (e.clientX / window.innerWidth - 0.5) * 2;
        mouseY = (e.clientY / window.innerHeight - 0.5) * 2;
      };

      window.addEventListener('mousemove', handleMouseMove);
    };

    init();

    return () => {
      disposed = true;
      if (renderer) {
        renderer.dispose();
      }
    };
  }, []);

  // AI Agent panel view
  if (showAgent && selectedAccount) {
    return (
      <div className="fixed inset-0 z-[80] flex items-end justify-center p-0 sm:items-center sm:p-6">
        <div className="absolute inset-0 bg-ink-950/90 backdrop-blur-sm" onClick={() => setShowAgent(false)} />
        <div className="relative flex max-h-[88vh] w-full max-w-[720px] flex-col overflow-hidden rounded-t-2xl border border-ink-700 bg-ink-900 sm:rounded-2xl">
          <div className="flex items-start justify-between gap-4 border-b border-ink-850 px-6 py-5">
            <div>
              <h2 className="font-display text-[18px] font-semibold tracking-tight text-chalk">AI Agent</h2>
              <p className="mt-1 text-[12px] text-chalk-faint">RAG-powered assistant for your email account</p>
            </div>
            <button onClick={() => setShowAgent(false)} className="rounded-lg p-1.5 text-chalk-faint hover:bg-ink-850 hover:text-chalk">
              <XIcon className="h-4 w-4" />
            </button>
          </div>
          <div className="p-4">
            <RAGAgentPanel
              emailAccountId={selectedAccount.id}
              leadName={selectedEmail ? getSenderFromEmail(selectedEmail)?.name || undefined : undefined}
              leadEmail={selectedEmail ? getSenderFromEmail(selectedEmail)?.email || undefined : undefined}
            />
          </div>
        </div>
      </div>
    );
  }

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
            <Link
              to={backTo}
              className="flex items-center gap-1.5 rounded-lg border border-ink-700 bg-ink-850 px-2.5 py-1.5 text-[12px] text-chalk-faint hover:border-ink-600 hover:text-chalk"
            >
              <ArrowLeftIcon className="h-3.5 w-3.5" />
              Back
            </Link>
            <span className="font-mono text-[11px] uppercase tracking-[0.16em] text-signal">
              Crawlio Email Agent
            </span>
          </div>
          {profile && (
            <button
              onClick={() => setShowSetup(false)}
              className="flex h-8 items-center gap-1.5 rounded-lg border border-ink-700 bg-ink-850 px-3 text-[12px] text-chalk-dim hover:border-ink-600 hover:text-chalk"
            >
              <XIcon className="h-3.5 w-3.5" />
              Cancel
            </button>
          )}
        </div>
        <BusinessOnboarding
          initial={showSetup && profile ? profile : null}
          onComplete={(p) => {
            setProfile(p);
            setShowSetup(false);
          }}
        />
      </div>
    );
  }

  return (
    <div className="relative mx-auto w-full max-w-[1460px] min-h-screen">
      {/* Three.js Background */}
      <div
        ref={canvasRef}
        className="fixed top-0 left-0 -z-10 h-full w-full opacity-10"
        style={{ height: '100vh' }}
      />

      <div className="px-4 py-4">
        {/* Thin toolbar */}
        <div className="mb-3 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Link
              to={backTo}
              className="flex items-center gap-1.5 rounded-lg border border-ink-700 bg-ink-850 px-2.5 py-1.5 text-[12px] text-chalk-faint hover:border-ink-600 hover:text-chalk"
            >
              <ArrowLeftIcon className="h-3.5 w-3.5" />
              Back
            </Link>
            <span className="font-mono text-[11px] uppercase tracking-[0.16em] text-signal">
              Crawlio Email Agent
            </span>
          </div>
          <div className="flex items-center gap-2">
            {accounts.map((account) => (
              <button
                key={account.id}
                onClick={() => {
                  setSelectedAccount(account);
                  setEmailPage(1);
                  resetConversation();
                }}
                className={cn(
                  'flex h-7 items-center gap-1.5 rounded-lg border px-2.5 text-[11px]',
                  selectedAccount?.id === account.id
                    ? 'border-signal/50 bg-signal/10 text-signal'
                    : 'border-ink-700 bg-ink-850 text-chalk-dim hover:border-ink-600'
                )}
              >
                {account.provider === 'google' ? '📧' : '📨'}
                {account.email_address}
              </button>
            ))}
            <button
              onClick={handleConnectGoogle}
              className="flex h-7 items-center gap-1 rounded-lg border border-ink-700 bg-ink-850 px-2 text-[11px] text-chalk-dim hover:border-ink-600"
            >
              <PlusIcon className="h-3 w-3" /> Gmail
            </button>
          </div>
        </div>

        {error && (
          <div className="mb-3 rounded-lg border border-ember/40 bg-ember/10 px-3 py-2 text-[12px] text-ember">
            {error}
          </div>
        )}

        {inboundError && (
          <div className="mb-3 rounded-lg border border-amber/40 bg-amber/10 px-3 py-2 text-[12px] text-amber">
            {inboundError}
            {inboundError.includes('expired') && (
              <button
                onClick={() => {
                  setInboundError(null);
                  void handleConnectGoogle();
                }}
                className="ml-2 underline hover:no-underline"
              >
                Reconnect Gmail
              </button>
            )}
          </div>
        )}

        {profile && (
          <div className="mb-3 flex flex-wrap items-center gap-1">
            {(
              [
                { id: 'inbox' as const, label: 'Inbox', icon: InboxIcon },
                { id: 'outreach' as const, label: 'Outreach', icon: SparklesIcon },
                { id: 'crm' as const, label: 'CRM', icon: UserIcon },
              ]
            ).map((tab) => (
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
                <tab.icon className="h-3.5 w-3.5" />
                {tab.label}
              </button>
            ))}
            <span className="mx-1 h-4 w-px bg-ink-800" />
            <button
              onClick={() => setShowSetup(true)}
              className="flex h-8 items-center gap-1.5 rounded-lg border border-ink-700 bg-ink-850 px-3 text-[12px] text-chalk-dim hover:border-ink-600 hover:text-chalk"
            >
              <SparklesIcon className="h-3.5 w-3.5" />
              Business Info
            </button>
          </div>
        )}

        {pageTab === 'inbox' && (<div className="grid grid-cols-[248px_1fr_1.15fr] gap-3" style={{ height: 'calc(100vh - 84px)' }}>
          {/* ===== SIDEBAR ===== */}
          <aside className="flex flex-col gap-3 overflow-y-auto rounded-2xl border border-ink-800 bg-ink-900/80 p-3">
            {/* AI actions */}
            <button
              onClick={() => setShowAgent(true)}
              className={cn(
                'flex h-9 w-full items-center justify-center gap-2 rounded-lg border text-[12px] font-medium',
                showAgent
                  ? 'border-signal/50 bg-signal/10 text-signal'
                  : 'border-signal/50 bg-signal/10 text-signal hover:bg-signal/20'
              )}
            >
              <SparklesIcon className="h-4 w-4" />
              AI Agent
            </button>
            <div className="grid grid-cols-2 gap-1.5">
              <button
                onClick={() => setComposeOpen(true)}
                className="flex h-8 items-center justify-center gap-1.5 rounded-lg border border-ink-700 bg-ink-850 text-[11px] text-chalk hover:border-ink-600 hover:bg-ink-800"
              >
                <MailIcon className="h-3.5 w-3.5" /> Compose
              </button>
              <button
                onClick={() => setWriteAIOpen(true)}
                className="flex h-8 items-center justify-center gap-1.5 rounded-lg border border-signal/50 bg-signal/10 text-[11px] text-signal hover:bg-signal/20"
              >
                <FileTextIcon className="h-3.5 w-3.5" /> Write AI
              </button>
            </div>

            {/* Folders */}
            <nav className="mt-2 space-y-0.5">
              {[
                { id: 'inbox' as const, label: 'Inbox', icon: InboxIcon },
                { id: 'sent' as const, label: 'Sent', icon: SendIcon },
                { id: 'trash' as const, label: 'Trash', icon: TrashIcon },
                { id: 'spam' as const, label: 'Spam', icon: ShieldAlertIcon },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => {
                    setActiveTab(tab.id);
                    setEmailPage(1);
                    setSelectedEmail(null);
                    resetConversation();
                  }}
                  className={cn(
                    'flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-[12px]',
                    activeTab === tab.id
                      ? 'bg-ink-850 text-chalk'
                      : 'text-chalk-dim hover:bg-ink-850/50 hover:text-chalk'
                  )}
                >
                  <tab.icon className="h-3.5 w-3.5" />
                  {tab.label}
                </button>
              ))}
            </nav>

            {/* Search */}
            <div className="mt-2 flex items-center gap-1 rounded-lg border border-ink-700 bg-ink-850 px-2">
              <SearchIcon className="h-3.5 w-3.5 text-chalk-dim" />
              <input
                type="text"
                placeholder="Search..."
                value={emailSearch}
                onChange={(e) => setEmailSearch(e.target.value)}
                className="h-7 w-full border-0 bg-transparent text-[12px] text-chalk placeholder:text-chalk-dim focus:outline-none"
              />
            </div>

            <div className="mt-2">
              <EmailQuotaBar quota={quota} />
            </div>

            {/* Booked meetings */}
            {bookedLeads.length > 0 && (
              <div className="mt-2 border-t border-ink-800 pt-2">
                <div className="mb-1 flex items-center justify-between">
                  <h4 className="text-[11px] font-medium text-chalk-dim">Booked Meetings</h4>
                  <button
                    onClick={handleExportCsv}
                    className="flex items-center gap-0.5 rounded border border-signal/30 bg-signal/10 px-1.5 py-0.5 text-[9px] text-signal hover:bg-signal/20"
                  >
                    <DownloadIcon className="h-2.5 w-2.5" /> CSV
                  </button>
                </div>
                <div className="space-y-1">
                  {bookedLeads.map((lead) => (
                    <div key={lead.id} className="rounded-lg border border-ink-800 bg-ink-850 p-1.5">
                      <p className="truncate text-[10px] font-medium text-chalk">{lead.subject || '(No subject)'}</p>
                      <div className="mt-0.5 flex items-center justify-between">
                        <span className="truncate text-[9px] text-chalk-faint">
                          {lead.lead_name || lead.lead_email || 'Unknown lead'}
                        </span>
                        <button
                          onClick={() => handleExportLeadToCrm(lead)}
                          className="rounded border border-signal/30 bg-signal/10 px-1 py-0.5 text-[8px] text-signal hover:bg-signal/20"
                        >
                          CRM
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </aside>

          {/* ===== EMAIL LIST (always visible) ===== */}
          <section className="flex min-h-0 flex-col overflow-hidden rounded-2xl border border-ink-800 bg-ink-900">
            <header className="flex items-center justify-between border-b border-ink-850 px-3 py-2">
              <span className="text-[11px] font-medium uppercase tracking-wide text-chalk-dim">
                {activeTab === 'inbox' ? 'Inbox' : activeTab === 'sent' ? 'Sent' : activeTab === 'spam' ? 'Spam' : 'Trash'}
              </span>
              {loadingEmails && <Loader2Icon className="h-3.5 w-3.5 animate-spin text-chalk-faint" />}
            </header>

            <div className="min-h-0 flex-1 overflow-y-auto">
              {activeTab === 'inbox'
                ? filteredPreviews.length === 0 && !loadingEmails
                  ? (
                    <div className="py-12 text-center">
                      <InboxIcon className="mx-auto h-10 w-10 text-ink-700" />
                      <p className="mt-2 text-[12px] text-chalk-dim">No conversations yet — new customer replies auto-start one here.</p>
                    </div>
                  )
                  : (
                    <div className="divide-y divide-ink-800/70">
                      {filteredPreviews.map((p) => {
                        const name = p.customer_name || p.customer_email || 'Unknown customer';
                        const initial = (name.charAt(0) || 'C').toUpperCase();
                        const isActive = conversation?.id === p.id;
                        return (
                          <div
                            key={p.id}
                            className={cn(
                              'flex cursor-pointer items-center gap-3 px-3 py-2 transition-colors',
                              isActive ? 'bg-ink-850' : 'hover:bg-ink-850/60',
                            )}
                            onClick={() => void openConversationFromPreview(p)}
                          >
                            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-ink-800 text-[10px] font-semibold text-chalk-dim">
                              {initial}
                            </span>
                            <div className="min-w-0 flex-1">
                              <div className="flex items-center justify-between gap-2">
                                <p className="truncate text-[12px] font-medium text-chalk">{name}</p>
                                <span className="whitespace-nowrap text-[10px] text-chalk-faint">
                                  {p.last_message_at ? khiTime(p.last_message_at) : ''}
                                </span>
                              </div>
                              <p className="truncate text-[11px] text-chalk-dim">
                                {p.last_message || 'No message yet...'}
                              </p>
                            </div>
                            {p.ai_agent_active && (
                              <span className="shrink-0 rounded-full border border-signal/30 bg-signal/10 px-1.5 py-0.25 text-[8px] text-signal">
                                AI
                              </span>
                            )}
                            {p.is_booked && (
                              <span className="shrink-0 rounded-full border border-amber/40 bg-amber/10 px-1.5 py-0.25 text-[8px] text-amber">
                                Booked
                              </span>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )
                : filteredEmails.length === 0 && !loadingEmails
                  ? (
                    <div className="py-12 text-center">
                      <InboxIcon className="mx-auto h-10 w-10 text-ink-700" />
                      <p className="mt-2 text-[12px] text-chalk-dim">
                        {activeTab === 'sent' ? 'No sent emails.' : activeTab === 'spam' ? 'No spam emails.' : 'Trash is empty.'}
                      </p>
                    </div>
                  )
                  : (
                    <div className="divide-y divide-ink-800/70">
                      {filteredEmails.map((email) => (
                        <div
                          key={email.id}
                          className={cn(
                            'flex cursor-pointer flex-col px-3 py-1.5 transition-colors hover:bg-ink-850/60',
                            (selectedEmail as unknown as EmailMessageDTO | null) !== null && (selectedEmail as unknown as EmailMessageDTO).id === email.id
                              ? 'bg-ink-850'
                              : ''
                          )}
                          onClick={() => {
                            void fetchEmailDetail(email.id);
                          }}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <p className="truncate text-[12px] font-medium text-chalk">{email.subject || '(No subject)'}</p>
                            <span className="whitespace-nowrap text-[10px] text-chalk-faint">
                              {email.date ? new Date(email.date).toLocaleDateString() : ''}
                            </span>
                          </div>
                          <p className="truncate text-[11px] text-chalk-dim">
                            {(() => {
                              if (activeTab === 'sent') {
                                const r = parseSender(email.to_email || '');
                                return (r && (r.name || r.email)) || 'Unknown recipient';
                              }
                              const s = getSenderFromEmail(email);
                              return (s && (s.name || s.email)) || 'Unknown sender';
                            })()}
                          </p>
                          <p className="truncate text-[10px] text-chalk-faint">{email.snippet || email.body_preview || 'No preview'}</p>
                        </div>
                      ))}
                    </div>
                  )}
            </div>

            <footer className="flex items-center justify-between gap-2 border-t border-ink-850 px-3 py-1.5">
              <button
                onClick={() => setEmailPage((p) => Math.max(1, p - 1))}
                disabled={emailPage <= 1 || loadingEmails}
                className="flex h-6 items-center gap-1 rounded border border-ink-700 bg-ink-850 px-2 text-[10px] text-chalk-dim hover:border-ink-600 hover:text-chalk disabled:opacity-40"
              >
                <ArrowLeftIcon className="h-3 w-3" /> Prev
              </button>
              <span className="text-[10px] text-chalk-faint">Page {emailPage}</span>
              <button
                onClick={() => setEmailPage((p) => p + 1)}
                disabled={!hasMoreEmails || loadingEmails}
                className="flex h-6 items-center gap-1 rounded border border-ink-700 bg-ink-850 px-2 text-[10px] text-chalk-dim hover:border-ink-600 hover:text-chalk disabled:opacity-40"
              >
                Next <ArrowLeftIcon className="h-3 w-3 rotate-180" />
              </button>
            </footer>
          </section>

          {/* ===== READING PANE (persists alongside list) ===== */}
          <section className="flex min-h-0 flex-col overflow-hidden rounded-2xl border border-ink-800 bg-ink-900">
            {selectedEmail === null ? (
              <div className="flex flex-1 items-center justify-center">
                <div className="text-center">
                  <MailIcon className="mx-auto h-9 w-9 text-ink-700" />
                  <p className="mt-2 text-[12px] text-chalk-dim">Select an email to read it here</p>
                </div>
              </div>
            ) : (
              <>
                <header className="flex items-start justify-between gap-2 border-b border-ink-850 px-4 py-3">
                  <div className="min-w-0 flex-1">
                    <h3 className="truncate text-[14px] font-semibold text-chalk">
                      {(selectedEmail as any).subject || '(No subject)'}
                    </h3>
                    <p className="mt-0.5 text-[11px] text-chalk-dim">
                      {activeTab === 'sent'
                        ? `To: ${formatSender(parseSender(selectedEmail.to_email || '')) || 'Unknown'}`
                        : `From: ${formatSender(getSenderFromEmail(selectedEmail)) || 'Unknown'}`}
                    </p>
                  </div>
                  <button
                    onClick={() => {
                      setSelectedEmail(null);
                      resetConversation();
                    }}
                    className="rounded-lg p-1 text-chalk-faint hover:bg-ink-850 hover:text-chalk"
                  >
                    <XIcon className="h-4 w-4" />
                  </button>
                </header>

                <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3">
                  <div className="whitespace-pre-wrap text-[12px] text-chalk-dim">
                    {htmlToPlainText((selectedEmail as any).body || (selectedEmail as any).snippet || 'No content')}
                  </div>
                </div>

                <div className="max-h-[46%] overflow-y-auto border-t border-ink-850 bg-ink-950 px-4 py-3">
                  {conversationStep === 'conversation' && (
                    <div className="space-y-2">
                      <div className="flex items-center justify-between rounded-lg border border-ink-800 bg-ink-850 px-2.5 py-1.5">
                        <span className="flex items-center gap-1.5 text-[11px] text-chalk">
                          <span className={cn('h-1.5 w-1.5 rounded-full', conversation?.ai_agent_active ? 'bg-signal animate-pulse' : 'bg-ink-600')} />
                          {profile?.business_name || 'AI'} Receptionist — {conversation?.ai_agent_active ? 'Active' : conversation ? 'Paused' : 'Idle'}
                        </span>
                        <div className="flex gap-1">
                          <button
                            onClick={() => document.getElementById('manual-reply-input')?.focus()}
                            className="flex h-6 items-center gap-1 rounded border border-ink-700 bg-ink-900 px-1.5 text-[10px] text-chalk hover:border-ink-600"
                          >
                            <MessageCircleIcon className="h-3 w-3" /> Reply
                          </button>
                          {conversation?.ai_agent_active ? (
                            <button
                              onClick={() => void handleStop()}
                              className="flex h-6 items-center gap-1 rounded border border-ink-700 bg-ink-900 px-1.5 text-[10px] text-chalk-dim hover:border-ink-600"
                            >
                              <StopCircleIcon className="h-3 w-3" /> Stop Crawlio
                            </button>
                          ) : (
                            <button
                              onClick={() => {
                                if (conversation) {
                                  void handleResume();
                                } else {
                                  void handleStartConversation();
                                }
                              }}
                              disabled={isGenerating}
                              className="flex h-6 items-center gap-1 rounded border border-signal/50 bg-signal/10 px-1.5 text-[10px] text-signal hover:bg-signal/20 disabled:opacity-50"
                            >
                              {isGenerating ? <Loader2Icon className="h-3 w-3 animate-spin" /> : <PlayIcon className="h-3 w-3" />}
                              Start Crawlio
                            </button>
                          )}
                        </div>
                      </div>

                      <div ref={chatScrollRef} className="h-72 space-y-2 overflow-y-auto py-1">
                        {!conversation ? (
                          <div className="py-8 text-center text-[11px] text-chalk-faint">
                            No conversation yet — press <span className="text-signal">Start Crawlio</span> to begin the AI receptionist for this email.
                          </div>
                        ) : messages.length === 0 ? (
                          <div className="py-8 text-center text-[11px] text-chalk-faint">
                            No messages yet — the AI agent replies to the customer here.
                          </div>
                        ) : (
                          messages.map((msg) => {
                            const isOutgoing = msg.sender_type === 'user' || msg.sender_type === 'ai';
                            const isSystem = msg.sender_type === 'system';
                            const label = isSystem
                              ? 'System'
                              : msg.sender_type === 'customer'
                              ? (conversation?.customer_name || conversation?.customer_email || 'Customer')
                              : msg.sender_type === 'ai'
                              ? 'AI Agent'
                              : 'You';
                            const initial = (label.charAt(0) || '?').toUpperCase();
                            const time = msg.created_at
                              ? khiTime(msg.created_at)
                              : '';
                            const isBooked = isSystem && msg.content.includes('Meeting booked');
                            return (
                              <div
                                key={msg.id}
                                className={cn(
                                  'flex items-end gap-1.5',
                                  isSystem ? 'justify-center' : isOutgoing ? 'justify-end' : 'justify-start'
                                )}
                              >
                                {!isSystem && !isOutgoing && (
                                  <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-ink-800 text-[9px] font-semibold text-chalk-dim">
                                    {initial}
                                  </div>
                                )}
                                <div className={cn('max-w-[82%]', isSystem && 'mx-auto')}>
                                  {!isSystem && (
                                    <div
                                      className={cn('mb-0.5 text-[9px] text-chalk-faint', isOutgoing ? 'text-right' : 'text-left')}
                                    >
                                      {label}
                                    </div>
                                  )}
                                  <div
                                    className={cn(
                                      'whitespace-pre-wrap break-words px-2.5 py-1.5 text-[11px]',
                                      isSystem
                                        ? 'rounded-full bg-amber/10 text-center text-amber/90'
                                        : isOutgoing
                                        ? 'rounded-2xl rounded-br-sm bg-signal/15 text-chalk'
                                        : 'rounded-2xl rounded-bl-sm bg-ink-850 text-chalk'
                                    )}
                                  >
                                    {msg.content}
                                    {!isSystem && (
                                      <span
                                        className={cn(
                                          'mt-0.5 block text-right text-[8px] leading-none text-chalk-faint/80'
                                        )}
                                      >
                                        {time}
                                      </span>
                                    )}
                                  </div>
                                  {isBooked && (
                                    <div className="mt-1 rounded-lg border border-signal/30 bg-signal/5 px-2 py-1">
                                      <p className="text-[9px] text-signal">Hot lead added to CRM. Meeting booked!</p>
                                    </div>
                                  )}
                                </div>
                                {!isSystem && isOutgoing && (
                                  <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-signal/20 text-[9px] font-semibold text-signal">
                                    {initial}
                                  </div>
                                )}
                              </div>
                            );
                          })
                        )}
                      </div>

                      <div className="flex items-end gap-1 pt-1">
                        <textarea
                          id="manual-reply-input"
                          value={manualReply}
                          onChange={(e) => setManualReply(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' && !e.shiftKey) {
                              e.preventDefault();
                              if (conversation && manualReply.trim() && !isSending) void handleManualReply();
                            }
                          }}
                          placeholder={conversation ? 'Type a message...' : 'Press Start Crawlio to begin the AI receptionist'}
                          rows={1}
                          disabled={!conversation}
                          className="min-h-[36px] max-h-24 flex-1 resize-none rounded-2xl rounded-br-sm border border-ink-700 bg-ink-900 px-3 py-2 text-[12px] text-chalk placeholder:text-chalk-faint focus:border-signal focus:outline-none disabled:opacity-50"
                        />
                        <button
                          onClick={() => void handleManualReply()}
                          disabled={isSending || !conversation || !manualReply.trim()}
                          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-signal/50 bg-signal/10 text-signal hover:bg-signal/20 disabled:opacity-50"
                        >
                          {isSending ? <Loader2Icon className="h-4 w-4 animate-spin" /> : <SendIcon className="h-4 w-4" />}
                        </button>
                      </div>
                    </div>
                  )}

                  {conversationStep === 'preview' && previewDraft && (
                    <div className="space-y-2">
                      {previewEditing ? (
                        <>
                          <div className="space-y-1.5">
                            <p className="text-[10px] font-medium text-chalk-dim">Subject</p>
                            <input
                              type="text"
                              value={editSubject}
                              onChange={(e) => setEditSubject(e.target.value)}
                              className="h-8 w-full rounded-lg border border-ink-700 bg-ink-950 px-2.5 text-[12px] text-chalk focus:border-signal focus:outline-none"
                            />
                            <p className="text-[10px] font-medium text-chalk-dim">Body</p>
                            <textarea
                              value={editBody}
                              onChange={(e) => setEditBody(e.target.value)}
                              rows={7}
                              className="w-full rounded-lg border border-ink-700 bg-ink-950 px-2.5 py-1.5 text-[12px] text-chalk focus:border-signal focus:outline-none"
                            />
                          </div>
                          <div className="flex justify-end gap-1.5">
                            <button onClick={() => setPreviewEditing(false)} className="flex h-7 items-center gap-1 rounded-lg border border-ink-700 bg-ink-850 px-2.5 text-[11px] text-chalk hover:border-ink-600">
                              <XIcon className="h-3 w-3" /> Cancel
                            </button>
                            <button onClick={handleSavePreview} disabled={isSavingEdit} className="flex h-7 items-center gap-1 rounded-lg border border-signal/50 bg-signal/10 px-2.5 text-[11px] text-signal hover:bg-signal/20 disabled:opacity-50">
                              {isSavingEdit ? <Loader2Icon className="h-3 w-3 animate-spin" /> : <CheckIcon className="h-3 w-3" />} Save
                            </button>
                          </div>
                        </>
                      ) : (
                        <>
                          <div className="rounded-lg border border-ink-800 bg-ink-850 p-2.5">
                            <p className="mb-0.5 text-[10px] font-medium text-chalk-dim">Subject</p>
                            <p className="text-[12px] text-chalk">{previewDraft.subject}</p>
                          </div>
                          <div
                            className="rounded-lg border border-ink-800 bg-ink-950 p-2.5 text-[12px] text-chalk-dim"
                            dangerouslySetInnerHTML={{ __html: previewDraft.body }}
                          />
                          <div className="flex justify-end gap-1.5">
                            <button onClick={() => setConversationStep('conversation')} className="flex h-7 items-center gap-1 rounded-lg border border-ink-700 bg-ink-850 px-2.5 text-[11px] text-chalk hover:border-ink-600">
                              <XIcon className="h-3 w-3" /> Cancel
                            </button>
                            <button onClick={handleStartEditPreview} className="flex h-7 items-center gap-1 rounded-lg border border-ink-700 bg-ink-850 px-2.5 text-[11px] text-chalk hover:border-ink-600">
                              <FileTextIcon className="h-3 w-3" /> Edit
                            </button>
                            <button onClick={handleApproveAndSend} className="flex h-7 items-center gap-1 rounded-lg border border-signal/50 bg-signal/10 px-2.5 text-[11px] text-signal hover:bg-signal/20">
                              <CheckIcon className="h-3 w-3" /> Send
                            </button>
                          </div>
                        </>
                      )}
                    </div>
                  )}

                  {conversationStep === 'booking' && (
                    <div className="space-y-2">
                      <div className="mx-auto flex h-9 w-9 items-center justify-center rounded-full border border-signal/30 bg-signal/10">
                        <CalendarIcon className="h-4 w-4 text-signal" />
                      </div>
                      <p className="text-center text-[12px] text-chalk">Meeting booked! Hot lead added to CRM.</p>
                      <div className="flex flex-col gap-1.5">
                        <button
                          onClick={() => {
                            if (selectedAccount) {
                              const n = prompt('Lead name:');
                              const e = prompt('Lead email:');
                              const d = prompt('Date (YYYY-MM-DD):');
                              const t = prompt('Time (HH:MM):');
                              if (n && e && d && t && selectedAccount) {
                                void handleBookMeeting({ name: n, email: e, company: '', date: d, time: t });
                              }
                            }
                          }}
                          className="flex h-8 items-center justify-center gap-1 rounded-lg border border-signal/50 bg-signal/10 text-[11px] text-signal hover:bg-signal/20"
                        >
                          <CalendarIcon className="h-3 w-3" /> Book Another
                        </button>
                        <button
                          onClick={handleExportCsv}
                          className="flex h-8 items-center justify-center gap-1 rounded-lg border border-signal/50 bg-signal/10 text-[11px] text-signal hover:bg-signal/20"
                        >
                          <DownloadIcon className="h-3 w-3" /> Download Booked Leads (CSV)
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </>
            )}
          </section>
        </div>)}

        {pageTab !== 'inbox' && profile && (
          <div className="grid grid-cols-[248px_1fr] gap-3" style={{ height: 'calc(100vh - 84px)' }}>
            <ActivityPanel />
            <div className="min-h-0 overflow-hidden rounded-2xl border border-ink-800 bg-ink-900">
              {pageTab === 'outreach' ? <OutreachTab /> : <CrmTab />}
            </div>
          </div>
        )}

        <ComposeDialog
          open={composeOpen}
          onClose={() => setComposeOpen(false)}
          selectedAccount={selectedAccount}
        />

        <WriteWithCrawlioDialog
          open={writeAIOpen}
          onClose={() => setWriteAIOpen(false)}
          selectedAccount={selectedAccount}
        />
      </div>
    </div>
  );
}
