import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '@clerk/clerk-react';
import { ArrowLeftIcon, MailIcon, PlusIcon, Loader2Icon, InboxIcon, SendIcon, TrashIcon, UserIcon } from 'lucide-react';
import { cn } from '../utils/cn';
import {
  listEmailAccounts,
  getGoogleAuthUrl,
  getMicrosoftAuthUrl,
  getEmailQuota,
  type EmailAccountDTO,
  type EmailQuotaDTO,
  type EmailMessageDTO,
} from '../../lib/api/emailAgent';
import { apiFetch, ApiError } from '../../lib/api/client';
import { ComposeDialog } from './ComposeDialog';
import { WriteWithCrawlioDialog } from './WriteWithCrawlioDialog';
import { RAGAgentPanel } from './RAGAgentPanel';
import { EmailQuotaBar } from './EmailQuotaBar';

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
  const [activeTab, setActiveTab] = useState<'inbox' | 'sent' | 'trash'>('inbox');
  const [emails, setEmails] = useState<EmailMessageDTO[]>([]);
  const [loadingEmails, setLoadingEmails] = useState(false);
  const [selectedEmail, setSelectedEmail] = useState<EmailMessageDTO | null>(null);
  const [showAgent, setShowAgent] = useState(false);

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
      const res = await apiFetch<{ items: EmailMessageDTO[] }>(
        `/api/v1/email-accounts/${selectedAccount.id}/${activeTab}`,
        token
      );
      setEmails(res.items);
    } catch (err) {
      console.error('Failed to load emails:', err);
    } finally {
      setLoadingEmails(false);
    }
  }, [getToken, selectedAccount, activeTab]);

  useEffect(() => {
    void fetchAccounts();
  }, []);

  useEffect(() => {
    void fetchQuota();
  }, [selectedAccount]);

  useEffect(() => {
    void fetchEmails();
  }, [selectedAccount, activeTab]);

  const handleConnectGoogle = async () => {
    try {
      const token = await getToken();
      const res = await getGoogleAuthUrl(token);
      window.location.href = res.auth_url;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to connect Google.');
    }
  };

  const handleConnectMicrosoft = async () => {
    try {
      const token = await getToken();
      const res = await getMicrosoftAuthUrl(token);
      window.location.href = res.auth_url;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to connect Microsoft.');
    }
  };

  return (
    <div className="mx-auto w-full max-w-[1180px]">
      <div className="mb-6 flex items-center justify-between gap-3">
        <Link
          to={backTo}
          className="flex items-center gap-1.5 text-[13px] text-chalk-faint hover:text-chalk"
        >
          <ArrowLeftIcon className="h-3.5 w-3.5" />
          Back to automation
        </Link>
        <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-signal">
          Crawlio.io Auto Email Agent
        </p>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-ember/40 bg-ember/10 px-3.5 py-2.5 text-[13px] text-ember">
          {error}
        </div>
      )}

      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setComposeOpen(true)}
            className="flex h-9 items-center gap-2 rounded-lg border border-ink-700 bg-ink-850 px-3 text-[13px] text-chalk hover:border-ink-600 hover:bg-ink-800"
          >
            <MailIcon className="h-4 w-4" />
            Compose
          </button>
          <button
            onClick={() => setWriteAIOpen(true)}
            className="flex h-9 items-center gap-2 rounded-lg border border-signal/50 bg-signal/10 px-3 text-[13px] text-signal hover:bg-signal/20"
          >
            <PlusIcon className="h-4 w-4" />
            Write with Crawlio
          </button>
          <button
            onClick={() => setShowAgent(!showAgent)}
            className={cn(
              'flex h-9 items-center gap-2 rounded-lg border px-3 text-[13px]',
              showAgent
                ? 'border-signal/50 bg-signal/10 text-signal'
                : 'border-ink-700 bg-ink-850 text-chalk hover:border-ink-600'
            )}
          >
            <UserIcon className="h-4 w-4" />
            AI Agent
          </button>
        </div>

        <div className="flex items-center gap-2">
          {accounts.map((account) => (
            <button
              key={account.id}
              onClick={() => setSelectedAccount(account)}
              className={cn(
                'flex h-8 items-center gap-2 rounded-lg border px-3 text-[12px]',
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
            className="flex h-8 items-center gap-1 rounded-lg border border-ink-700 bg-ink-850 px-2 text-[12px] text-chalk-dim hover:border-ink-600"
          >
            <PlusIcon className="h-3 w-3" />
            Gmail
          </button>
          <button
            onClick={handleConnectMicrosoft}
            className="flex h-8 items-center gap-1 rounded-lg border border-ink-700 bg-ink-850 px-2 text-[12px] text-chalk-dim hover:border-ink-600"
          >
            <PlusIcon className="h-3 w-3" />
            Outlook
          </button>
        </div>
      </div>

      <div className="grid grid-cols-[200px_1fr] gap-4">
        <div className="rounded-2xl border border-ink-800 bg-ink-900 p-4">
          <nav className="space-y-1">
            {[
              { id: 'inbox' as const, label: 'Inbox', icon: InboxIcon },
              { id: 'sent' as const, label: 'Sent', icon: SendIcon },
              { id: 'trash' as const, label: 'Trash', icon: TrashIcon },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  'flex w-full items-center gap-2 rounded-lg px-3 py-2 text-[13px]',
                  activeTab === tab.id
                    ? 'bg-ink-850 text-chalk'
                    : 'text-chalk-dim hover:bg-ink-850/50 hover:text-chalk'
                )}
              >
                <tab.icon className="h-4 w-4" />
                {tab.label}
              </button>
            ))}
          </nav>

          <div className="mt-6">
            <EmailQuotaBar quota={quota} />
          </div>
        </div>

        <div className="rounded-2xl border border-ink-800 bg-ink-900">
          {showAgent && selectedAccount ? (
            <div className="p-4">
              <RAGAgentPanel
                emailAccountId={selectedAccount.id}
                leadName=""
                leadCompany=""
              />
            </div>
          ) : isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2Icon className="h-6 w-6 animate-spin text-chalk-faint" />
            </div>
          ) : accounts.length === 0 ? (
            <div className="py-12 text-center">
              <MailIcon className="mx-auto h-12 w-12 text-ink-700" />
              <h3 className="mt-4 text-[16px] font-medium text-chalk">No email accounts connected</h3>
              <p className="mt-2 text-[13px] text-chalk-dim">
                Connect your Gmail or Outlook account to start sending emails.
              </p>
              <div className="mt-4 flex justify-center gap-2">
                <button
                  onClick={handleConnectGoogle}
                  className="flex h-9 items-center gap-2 rounded-lg border border-ink-700 bg-ink-850 px-4 text-[13px] text-chalk hover:border-ink-600"
                >
                  Connect Gmail
                </button>
                <button
                  onClick={handleConnectMicrosoft}
                  className="flex h-9 items-center gap-2 rounded-lg border border-ink-700 bg-ink-850 px-4 text-[13px] text-chalk hover:border-ink-600"
                >
                  Connect Outlook
                </button>
              </div>
            </div>
          ) : (
            <div>
              {loadingEmails ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2Icon className="h-6 w-6 animate-spin text-chalk-faint" />
                </div>
              ) : emails.length === 0 ? (
                <div className="py-12 text-center">
                  <InboxIcon className="mx-auto h-12 w-12 text-ink-700" />
                  <h3 className="mt-4 text-[16px] font-medium text-chalk">
                    {activeTab === 'inbox' ? 'Inbox' : activeTab === 'sent' ? 'Sent' : 'Trash'}
                  </h3>
                  <p className="mt-2 text-[13px] text-chalk-dim">
                    {activeTab === 'inbox'
                      ? 'Your inbox emails will appear here.'
                      : activeTab === 'sent'
                      ? 'Sent emails will appear here.'
                      : 'Trashed emails will appear here.'}
                  </p>
                </div>
              ) : (
                <div className="divide-y divide-ink-800">
                  {emails.map((email) => (
                    <button
                      key={email.id}
                      onClick={() => setSelectedEmail(email)}
                      className={cn(
                        'w-full p-4 text-left hover:bg-ink-850/50 transition-colors',
                        selectedEmail?.id === email.id && 'bg-ink-850'
                      )}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="min-w-0 flex-1">
                          <p className="text-[13px] font-medium text-chalk truncate">
                            {email.subject || '(No subject)'}
                          </p>
                          <p className="text-[12px] text-chalk-dim truncate">
                            {email.from_email || 'Unknown sender'}
                          </p>
                        </div>
                        <span className="text-[11px] text-chalk-faint whitespace-nowrap">
                          {email.date ? new Date(email.date).toLocaleDateString() : ''}
                        </span>
                      </div>
                      <p className="mt-1 text-[12px] text-chalk-faint truncate">
                        {email.body_preview || email.snippet || 'No preview'}
                      </p>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

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
  );
}
