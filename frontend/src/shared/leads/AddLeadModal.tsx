import React, { useState } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { AnimatePresence, motion } from 'framer-motion';
import { Loader2Icon, XIcon } from 'lucide-react';
import { Button } from '../ui/Button';
import { createLead } from '../../lib/api/leads';
import { ApiError } from '../../lib/api/client';

interface Props {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}

export function AddLeadModal({ open, onClose, onCreated }: Props) {
  const { getToken } = useAuth();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [website, setWebsite] = useState('');
  const [address, setAddress] = useState('');
  const [industry, setIndustry] = useState('');
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reset = () => {
    setName('');
    setEmail('');
    setPhone('');
    setWebsite('');
    setAddress('');
    setIndustry('');
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
      await createLead(token, {
        name,
        email: email || undefined,
        phone: phone || undefined,
        website: website || undefined,
        address: address || undefined,
        industry: industry || undefined,
        source: 'Manual entry'
      });
      reset();
      onCreated();
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
          aria-labelledby="add-lead-title"
          initial={{ opacity: 0, y: 24, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 16, scale: 0.98 }}
          transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
          className="relative flex max-h-[88vh] w-full max-w-[480px] flex-col overflow-hidden rounded-t-2xl border border-ink-700 bg-ink-900 sm:rounded-2xl">

            <div className="flex items-start justify-between gap-4 border-b border-ink-850 px-6 py-5">
              <h2 id="add-lead-title" className="font-display text-[18px] font-semibold tracking-tight text-chalk">
                Add lead
              </h2>
              <button
              type="button"
              onClick={handleClose}
              aria-label="Close dialog"
              className="rounded-lg p-1.5 text-chalk-faint hover:bg-ink-850 hover:text-chalk">

                <XIcon className="h-4 w-4" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="flex min-h-0 flex-1 flex-col">
              <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-6 py-5 scrollbar-slim">
              <div>
                <label htmlFor="lead-name" className="mb-1.5 block text-[13px] font-medium text-chalk-dim">
                  Full name
                </label>
                <input
                  id="lead-name"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Amara Okafor"
                  className="h-11 w-full rounded-lg border border-ink-700 bg-ink-950 px-3.5 text-[14px] text-chalk placeholder:text-chalk-faint focus:border-signal focus:outline-none" />

              </div>
              <div>
                <label htmlFor="lead-email" className="mb-1.5 block text-[13px] font-medium text-chalk-dim">
                  Email
                </label>
                <input
                  id="lead-email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="amara@northwind.co"
                  className="h-11 w-full rounded-lg border border-ink-700 bg-ink-950 px-3.5 text-[14px] text-chalk placeholder:text-chalk-faint focus:border-signal focus:outline-none" />

              </div>
              <div>
                <label htmlFor="lead-phone" className="mb-1.5 block text-[13px] font-medium text-chalk-dim">
                  Phone
                </label>
                <input
                  id="lead-phone"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="+1 415 555 0132"
                  className="h-11 w-full rounded-lg border border-ink-700 bg-ink-950 px-3.5 text-[14px] text-chalk placeholder:text-chalk-faint focus:border-signal focus:outline-none" />

              </div>
              <div>
                <label htmlFor="lead-website" className="mb-1.5 block text-[13px] font-medium text-chalk-dim">
                  Website
                </label>
                <input
                  id="lead-website"
                  value={website}
                  onChange={(e) => setWebsite(e.target.value)}
                  placeholder="https://northwind.co"
                  className="h-11 w-full rounded-lg border border-ink-700 bg-ink-950 px-3.5 text-[14px] text-chalk placeholder:text-chalk-faint focus:border-signal focus:outline-none" />

              </div>
              <div>
                <label htmlFor="lead-address" className="mb-1.5 block text-[13px] font-medium text-chalk-dim">
                  Address
                </label>
                <input
                  id="lead-address"
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  placeholder="221B Baker Street, London"
                  className="h-11 w-full rounded-lg border border-ink-700 bg-ink-950 px-3.5 text-[14px] text-chalk placeholder:text-chalk-faint focus:border-signal focus:outline-none" />

              </div>
              <div>
                <label htmlFor="lead-industry" className="mb-1.5 block text-[13px] font-medium text-chalk-dim">
                  Industry
                </label>
                <input
                  id="lead-industry"
                  value={industry}
                  onChange={(e) => setIndustry(e.target.value)}
                  placeholder="Dental Clinic"
                  className="h-11 w-full rounded-lg border border-ink-700 bg-ink-950 px-3.5 text-[14px] text-chalk placeholder:text-chalk-faint focus:border-signal focus:outline-none" />

              </div>

              {error &&
              <p role="alert" className="rounded-lg border border-ember/40 bg-ember/10 px-3.5 py-2.5 text-[13px] text-ember">
                  {error}
                </p>
              }
              </div>

              <div className="flex justify-end gap-2 border-t border-ink-850 px-6 py-4">
                <Button type="button" variant="outline" onClick={handleClose}>
                  Cancel
                </Button>
                <Button type="submit" disabled={isPending}>
                  {isPending && <Loader2Icon className="h-4 w-4 animate-spin" />}
                  {isPending ? 'Adding…' : 'Add lead'}
                </Button>
              </div>
            </form>
          </motion.div>
        </div>
      }
    </AnimatePresence>);

}
