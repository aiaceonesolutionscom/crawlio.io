import React, { useState } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { AnimatePresence, motion } from 'framer-motion';
import { Loader2Icon, XIcon } from 'lucide-react';
import { Button } from '../../../shared/ui/Button';
import { inviteMember, type TeamRole } from '../../../lib/api/team';
import { ApiError } from '../../../lib/api/client';

interface Props {
  open: boolean;
  onClose: () => void;
  onInvited: () => void;
}

export function InviteMemberModal({ open, onClose, onInvited }: Props) {
  const { getToken } = useAuth();
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<TeamRole>('Member');
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reset = () => {
    setEmail('');
    setRole('Member');
    setError(null);
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsPending(true);
    setError(null);
    try {
      const token = await getToken();
      await inviteMember(token, email, role);
      reset();
      onInvited();
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong.');
    } finally {
      setIsPending(false);
    }
  };

  return (
    <AnimatePresence>
      {open &&
      <div className="fixed inset-0 z-[60] flex items-end justify-center p-0 sm:items-center sm:p-6">
          <motion.button
          type="button"
          aria-label="Close"
          onClick={handleClose}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="absolute inset-0 bg-ink-950/85 backdrop-blur-sm" />

          <motion.div
          role="dialog"
          aria-modal="true"
          aria-labelledby="invite-member-title"
          initial={{ opacity: 0, y: 24, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 16, scale: 0.98 }}
          transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
          className="relative w-full max-w-[440px] overflow-hidden rounded-t-2xl border border-ink-700 bg-ink-900 sm:rounded-2xl">

            <div className="flex items-start justify-between gap-4 border-b border-ink-850 px-6 py-5">
              <h2 id="invite-member-title" className="font-display text-[18px] font-semibold tracking-tight text-chalk">
                Invite member
              </h2>
              <button
              type="button"
              onClick={handleClose}
              aria-label="Close dialog"
              className="rounded-lg p-1.5 text-chalk-faint hover:bg-ink-850 hover:text-chalk">

                <XIcon className="h-4 w-4" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4 px-6 py-5">
              <div>
                <label htmlFor="invite-email" className="mb-1.5 block text-[13px] font-medium text-chalk-dim">
                  Email address
                </label>
                <input
                  id="invite-email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="teammate@company.com"
                  className="h-11 w-full rounded-lg border border-ink-700 bg-ink-950 px-3.5 text-[14px] text-chalk placeholder:text-chalk-faint focus:border-signal focus:outline-none" />

              </div>
              <div>
                <label htmlFor="invite-role" className="mb-1.5 block text-[13px] font-medium text-chalk-dim">
                  Role
                </label>
                <select
                  id="invite-role"
                  value={role}
                  onChange={(e) => setRole(e.target.value as TeamRole)}
                  className="h-11 w-full rounded-lg border border-ink-700 bg-ink-950 px-3.5 text-[14px] text-chalk focus:border-signal focus:outline-none">

                  <option value="Member">Member</option>
                  <option value="Admin">Admin</option>
                </select>
              </div>

              {error &&
              <p role="alert" className="rounded-lg border border-ember/40 bg-ember/10 px-3.5 py-2.5 text-[13px] text-ember">
                  {error}
                </p>
              }

              <div className="flex justify-end gap-2 pt-2">
                <Button type="button" variant="outline" onClick={handleClose}>
                  Cancel
                </Button>
                <Button type="submit" disabled={isPending}>
                  {isPending && <Loader2Icon className="h-4 w-4 animate-spin" />}
                  {isPending ? 'Inviting…' : 'Send invite'}
                </Button>
              </div>
            </form>
          </motion.div>
        </div>
      }
    </AnimatePresence>);

}
