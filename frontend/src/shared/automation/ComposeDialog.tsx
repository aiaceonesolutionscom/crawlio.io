import React, { useState } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { XIcon, Loader2Icon, MailIcon } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { createEmailDraft, sendEmailDraft, type EmailAccountDTO } from '../../lib/api/emailAgent';
import { ApiError } from '../../lib/api/client';

interface Props {
  open: boolean;
  onClose: () => void;
  selectedAccount: EmailAccountDTO | null;
}

export function ComposeDialog({ open, onClose, selectedAccount }: Props) {
  const { getToken } = useAuth();
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [recipients, setRecipients] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const reset = () => {
    setSubject('');
    setBody('');
    setRecipients('');
    setError(null);
    setSuccess(false);
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedAccount) {
      setError('Please select an email account first.');
      return;
    }

    setIsSending(true);
    setError(null);

    try {
      const token = await getToken();
      const recipientList = recipients
        .split(',')
        .map((r) => r.trim())
        .filter((r) => r.length > 0);

      if (recipientList.length === 0) {
        setError('Please add at least one recipient.');
        setIsSending(false);
        return;
      }

      const draft = await createEmailDraft(token, {
        email_account_id: selectedAccount.id,
        subject,
        body,
        kind: 'composed',
        recipient_emails: recipientList,
      });

      await sendEmailDraft(token, draft.id);
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
            aria-labelledby="compose-title"
            initial={{ opacity: 0, y: 24, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.98 }}
            transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
            className="relative flex max-h-[88vh] w-full max-w-[520px] flex-col overflow-hidden rounded-t-2xl border border-ink-700 bg-ink-900 sm:rounded-2xl"
          >
            <div className="flex items-start justify-between gap-4 border-b border-ink-850 px-6 py-5">
              <h2 id="compose-title" className="flex items-center gap-2 font-display text-[18px] font-semibold tracking-tight text-chalk">
                <MailIcon className="h-5 w-5 text-signal" />
                Compose Email
              </h2>
              <button onClick={handleClose} className="rounded-lg p-1.5 text-chalk-faint hover:bg-ink-850 hover:text-chalk">
                <XIcon className="h-4 w-4" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="flex min-h-0 flex-1 flex-col">
              <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-6 py-5 scrollbar-slim">
                {success ? (
                  <div className="rounded-lg border border-signal/40 bg-signal/10 px-3.5 py-2.5 text-[13px] text-signal">
                    Email sent successfully!
                  </div>
                ) : (
                  <>
                    <div>
                      <label className="mb-1.5 block text-[13px] font-medium text-chalk-dim">To</label>
                      <input
                        type="text"
                        value={recipients}
                        onChange={(e) => setRecipients(e.target.value)}
                        placeholder="email1@example.com, email2@example.com"
                        className="h-11 w-full rounded-lg border border-ink-700 bg-ink-950 px-3.5 text-[14px] text-chalk placeholder:text-chalk-faint focus:border-signal focus:outline-none"
                      />
                    </div>

                    <div>
                      <label className="mb-1.5 block text-[13px] font-medium text-chalk-dim">Subject</label>
                      <input
                        type="text"
                        value={subject}
                        onChange={(e) => setSubject(e.target.value)}
                        placeholder="Email subject"
                        className="h-11 w-full rounded-lg border border-ink-700 bg-ink-950 px-3.5 text-[14px] text-chalk placeholder:text-chalk-faint focus:border-signal focus:outline-none"
                        required
                      />
                    </div>

                    <div>
                      <label className="mb-1.5 block text-[13px] font-medium text-chalk-dim">Body</label>
                      <textarea
                        value={body}
                        onChange={(e) => setBody(e.target.value)}
                        placeholder="Write your email here..."
                        rows={8}
                        className="w-full rounded-lg border border-ink-700 bg-ink-950 px-3.5 py-2.5 text-[14px] text-chalk placeholder:text-chalk-faint focus:border-signal focus:outline-none"
                        required
                      />
                    </div>

                    {error && (
                      <p role="alert" className="rounded-lg border border-ember/40 bg-ember/10 px-3.5 py-2.5 text-[13px] text-ember">
                        {error}
                      </p>
                    )}
                  </>
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
                {!success && (
                  <button
                    type="submit"
                    disabled={isSending}
                    className="flex h-9 items-center gap-2 rounded-lg border border-signal/50 bg-signal/10 px-4 text-[13px] text-signal hover:bg-signal/20 disabled:opacity-50"
                  >
                    {isSending && <Loader2Icon className="h-4 w-4 animate-spin" />}
                    {isSending ? 'Sending...' : 'Send Email'}
                  </button>
                )}
              </div>
            </form>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
