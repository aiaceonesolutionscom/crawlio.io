import React, { useState } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { XIcon, Loader2Icon, SparklesIcon, CheckIcon } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { generateAIEmail, approveAIEmail, type EmailAccountDTO, type EmailDraftDTO } from '../../lib/api/emailAgent';
import { ApiError } from '../../lib/api/client';

interface Props {
  open: boolean;
  onClose: () => void;
  selectedAccount: EmailAccountDTO | null;
}

export function WriteWithCrawlioDialog({ open, onClose, selectedAccount }: Props) {
  const { getToken } = useAuth();
  const [prompt, setPrompt] = useState('');
  const [leadName, setLeadName] = useState('');
  const [leadCompany, setLeadCompany] = useState('');
  const [leadEmail, setLeadEmail] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [generatedDraft, setGeneratedDraft] = useState<EmailDraftDTO | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const reset = () => {
    setPrompt('');
    setLeadName('');
    setLeadCompany('');
    setLeadEmail('');
    setGeneratedDraft(null);
    setError(null);
    setSuccess(false);
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const handleGenerate = async () => {
    if (!selectedAccount) {
      setError('Please select an email account first.');
      return;
    }

    setIsGenerating(true);
    setError(null);

    try {
      const token = await getToken();
      const draft = await generateAIEmail(token, {
        email_account_id: selectedAccount.id,
        prompt,
        lead_name: leadName,
        lead_company: leadCompany,
        lead_email: leadEmail,
      });
      setGeneratedDraft(draft);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to generate email.');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleApprove = async () => {
    if (!generatedDraft) return;

    setIsSending(true);
    setError(null);

    try {
      const token = await getToken();
      await approveAIEmail(token, generatedDraft.id);
      setSuccess(true);
      setTimeout(handleClose, 1500);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to send email.');
    } finally {
      setIsSending(false);
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-[60] flex items-end justify-center p-0 sm:items-center sm:p-6">
          <motion.button
            onClick={handleClose}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 bg-ink-950/85 backdrop-blur-sm"
          />
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-labelledby="write-ai-title"
            initial={{ opacity: 0, y: 24, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.98 }}
            transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
            className="relative flex max-h-[88vh] w-full max-w-[580px] flex-col overflow-hidden rounded-t-2xl border border-ink-700 bg-ink-900 sm:rounded-2xl"
          >
            <div className="flex items-start justify-between gap-4 border-b border-ink-850 px-6 py-5">
              <h2 id="write-ai-title" className="flex items-center gap-2 font-display text-[18px] font-semibold tracking-tight text-chalk">
                <SparklesIcon className="h-5 w-5 text-signal" />
                Write with Crawlio
              </h2>
              <button onClick={handleClose} className="rounded-lg p-1.5 text-chalk-faint hover:bg-ink-850 hover:text-chalk">
                <XIcon className="h-4 w-4" />
              </button>
            </div>

            <div className="flex min-h-0 flex-1 flex-col">
              <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-6 py-5 scrollbar-slim">
                {success ? (
                  <div className="rounded-lg border border-signal/40 bg-signal/10 px-3.5 py-2.5 text-[13px] text-signal">
                    AI email sent successfully!
                  </div>
                ) : generatedDraft ? (
                  <div className="space-y-4">
                    <div className="rounded-lg border border-signal/30 bg-signal/5 p-4">
                      <p className="mb-2 text-[12px] font-medium text-signal">AI Generated Email</p>
                      <div className="space-y-2">
                        <div>
                          <p className="text-[11px] text-chalk-faint">Subject</p>
                          <p className="text-[14px] text-chalk">{generatedDraft.subject}</p>
                        </div>
                        <div>
                          <p className="text-[11px] text-chalk-faint">Body</p>
                          <div
                            className="mt-1 rounded-lg border border-ink-700 bg-ink-950 p-3 text-[13px] text-chalk-dim"
                            dangerouslySetInnerHTML={{ __html: generatedDraft.body }}
                          />
                        </div>
                      </div>
                    </div>

                    <div className="flex justify-end gap-2">
                      <button
                        onClick={() => setGeneratedDraft(null)}
                        className="flex h-9 items-center rounded-lg border border-ink-700 bg-ink-850 px-4 text-[13px] text-chalk hover:border-ink-600"
                      >
                        Edit with Crawlio
                      </button>
                      <button
                        onClick={handleApprove}
                        disabled={isSending}
                        className="flex h-9 items-center gap-2 rounded-lg border border-signal/50 bg-signal/10 px-4 text-[13px] text-signal hover:bg-signal/20 disabled:opacity-50"
                      >
                        {isSending ? (
                          <Loader2Icon className="h-4 w-4 animate-spin" />
                        ) : (
                          <CheckIcon className="h-4 w-4" />
                        )}
                        {isSending ? 'Sending...' : 'Approve & Send'}
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div>
                      <label className="mb-1.5 block text-[13px] font-medium text-chalk-dim">What to write about</label>
                      <textarea
                        value={prompt}
                        onChange={(e) => setPrompt(e.target.value)}
                        placeholder="Describe what you want to write about... e.g., 'Promote our new SEO service to potential clients'"
                        rows={3}
                        className="w-full rounded-lg border border-ink-700 bg-ink-950 px-3.5 py-2.5 text-[14px] text-chalk placeholder:text-chalk-faint focus:border-signal focus:outline-none"
                      />
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="mb-1.5 block text-[13px] font-medium text-chalk-dim">Lead Name</label>
                        <input
                          type="text"
                          value={leadName}
                          onChange={(e) => setLeadName(e.target.value)}
                          placeholder="John Doe"
                          className="h-11 w-full rounded-lg border border-ink-700 bg-ink-950 px-3.5 text-[14px] text-chalk placeholder:text-chalk-faint focus:border-signal focus:outline-none"
                        />
                      </div>
                      <div>
                        <label className="mb-1.5 block text-[13px] font-medium text-chalk-dim">Company</label>
                        <input
                          type="text"
                          value={leadCompany}
                          onChange={(e) => setLeadCompany(e.target.value)}
                          placeholder="Acme Inc"
                          className="h-11 w-full rounded-lg border border-ink-700 bg-ink-950 px-3.5 text-[14px] text-chalk placeholder:text-chalk-faint focus:border-signal focus:outline-none"
                        />
                      </div>
                    </div>

                    <div>
                      <label className="mb-1.5 block text-[13px] font-medium text-chalk-dim">Lead Email</label>
                      <input
                        type="email"
                        value={leadEmail}
                        onChange={(e) => setLeadEmail(e.target.value)}
                        placeholder="john@example.com"
                        className="h-11 w-full rounded-lg border border-ink-700 bg-ink-950 px-3.5 text-[14px] text-chalk placeholder:text-chalk-faint focus:border-signal focus:outline-none"
                      />
                    </div>

                    {error && (
                      <p role="alert" className="rounded-lg border border-ember/40 bg-ember/10 px-3.5 py-2.5 text-[13px] text-ember">
                        {error}
                      </p>
                    )}
                  </div>
                )}
              </div>

              <div className="flex justify-end gap-2 border-t border-ink-850 px-6 py-4">
                <button
                  type="button"
                  onClick={handleClose}
                  className="flex h-9 items-center rounded-lg border border-ink-700 bg-ink-850 px-4 text-[13px] text-chalk hover:border-ink-600"
                >
                  Cancel
                </button>
                {!generatedDraft && !success && (
                  <button
                    onClick={handleGenerate}
                    disabled={isGenerating || !prompt}
                    className="flex h-9 items-center gap-2 rounded-lg border border-signal/50 bg-signal/10 px-4 text-[13px] text-signal hover:bg-signal/20 disabled:opacity-50"
                  >
                    {isGenerating ? (
                      <Loader2Icon className="h-4 w-4 animate-spin" />
                    ) : (
                      <SparklesIcon className="h-4 w-4" />
                    )}
                    {isGenerating ? 'Generating...' : 'Generate with AI'}
                  </button>
                )}
              </div>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
