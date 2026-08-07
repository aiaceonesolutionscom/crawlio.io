import React, { useEffect, useState } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { AnimatePresence, motion } from 'framer-motion';
import { ExternalLinkIcon, Loader2Icon, MapPinIcon, XIcon } from 'lucide-react';
import { Button } from '../ui/Button';
import { updateLead, type LeadDTO } from '../../lib/api/leads';
import { ApiError } from '../../lib/api/client';
import type { LeadStatus } from '../../types';

const STATUSES: LeadStatus[] = ['New', 'Qualified', 'Contacted', 'Nurturing', 'Won', 'Lost'];

interface Props {
  lead: LeadDTO | null;
  onClose: () => void;
  onUpdated: () => void;
}

export function EditLeadModal({ lead, onClose, onUpdated }: Props) {
  const { getToken } = useAuth();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [website, setWebsite] = useState('');
  const [address, setAddress] = useState('');
  const [industry, setIndustry] = useState('');
  const [status, setStatus] = useState<LeadStatus>('New');
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!lead) return;
    setName(lead.name);
    setEmail(lead.email ?? '');
    setPhone(lead.phone ?? '');
    setWebsite(lead.website ?? '');
    setAddress(lead.address ?? '');
    setIndustry(lead.industry ?? '');
    setStatus(lead.status);
    setError(null);
  }, [lead]);

  const handleClose = () => {
    setError(null);
    onClose();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!lead) return;
    setIsPending(true);
    setError(null);
    try {
      const token = await getToken();
      await updateLead(token, lead.id, {
        name,
        email: email || undefined,
        phone: phone || undefined,
        website: website || undefined,
        address: address || undefined,
        industry: industry || undefined,
        status
      });
      onUpdated();
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong.');
    } finally {
      setIsPending(false);
    }
  };

  return (
    <AnimatePresence>
      {lead &&
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
          aria-labelledby="edit-lead-title"
          initial={{ opacity: 0, y: 24, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 16, scale: 0.98 }}
          transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
          className="relative flex max-h-[88vh] w-full max-w-[480px] flex-col overflow-hidden rounded-t-2xl border border-ink-700 bg-ink-900 sm:rounded-2xl">

            <div className="flex items-start justify-between gap-4 border-b border-ink-850 px-6 py-5">
              <h2 id="edit-lead-title" className="font-display text-[18px] font-semibold tracking-tight text-chalk">
                Edit lead
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
                <label htmlFor="edit-lead-name" className="mb-1.5 block text-[13px] font-medium text-chalk-dim">
                  Full name
                </label>
                <input
                  id="edit-lead-name"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="h-11 w-full rounded-lg border border-ink-700 bg-ink-950 px-3.5 text-[14px] text-chalk focus:border-signal focus:outline-none" />

              </div>
              <div>
                <label htmlFor="edit-lead-email" className="mb-1.5 block text-[13px] font-medium text-chalk-dim">
                  Email
                </label>
                <input
                  id="edit-lead-email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="h-11 w-full rounded-lg border border-ink-700 bg-ink-950 px-3.5 text-[14px] text-chalk focus:border-signal focus:outline-none" />

              </div>
              <div>
                <label htmlFor="edit-lead-phone" className="mb-1.5 block text-[13px] font-medium text-chalk-dim">
                  Phone
                </label>
                <input
                  id="edit-lead-phone"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  className="h-11 w-full rounded-lg border border-ink-700 bg-ink-950 px-3.5 text-[14px] text-chalk focus:border-signal focus:outline-none" />

              </div>
              <div>
                <div className="mb-1.5 flex items-center justify-between">
                  <label htmlFor="edit-lead-website" className="block text-[13px] font-medium text-chalk-dim">
                    Website
                  </label>
                  {website &&
                  <a
                    href={/^https?:\/\//.test(website) ? website : `https://${website}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    title="Open website"
                    className="flex items-center gap-1 text-[12px] text-signal hover:underline">

                      <ExternalLinkIcon className="h-3 w-3" /> View
                    </a>
                  }
                </div>
                <input
                  id="edit-lead-website"
                  value={website}
                  onChange={(e) => setWebsite(e.target.value)}
                  className="h-11 w-full rounded-lg border border-ink-700 bg-ink-950 px-3.5 text-[14px] text-chalk focus:border-signal focus:outline-none" />

              </div>
              <div>
                <div className="mb-1.5 flex items-center justify-between">
                  <label htmlFor="edit-lead-address" className="block text-[13px] font-medium text-chalk-dim">
                    Address
                  </label>
                  {address &&
                  <a
                    href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(address)}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    title="Open in Google Maps"
                    className="flex items-center gap-1 text-[12px] text-signal hover:underline">

                      <MapPinIcon className="h-3 w-3" /> View on map
                    </a>
                  }
                </div>
                <input
                  id="edit-lead-address"
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  className="h-11 w-full rounded-lg border border-ink-700 bg-ink-950 px-3.5 text-[14px] text-chalk focus:border-signal focus:outline-none" />

              </div>
              <div>
                <label htmlFor="edit-lead-industry" className="mb-1.5 block text-[13px] font-medium text-chalk-dim">
                  Industry
                </label>
                <input
                  id="edit-lead-industry"
                  value={industry}
                  onChange={(e) => setIndustry(e.target.value)}
                  className="h-11 w-full rounded-lg border border-ink-700 bg-ink-950 px-3.5 text-[14px] text-chalk focus:border-signal focus:outline-none" />

              </div>
              {lead && Object.keys(lead.social_links ?? {}).length > 0 &&
              <div>
                  <p className="mb-1.5 text-[13px] font-medium text-chalk-dim">Social links</p>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(lead.social_links).map(([platform, url]) =>
                  <a
                    key={platform}
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="rounded-full border border-ink-700 px-3 py-1 text-[12px] capitalize text-signal hover:border-signal/50 hover:underline">

                        {platform}
                      </a>
                  )}
                  </div>
                </div>
              }
              <div>
                <label htmlFor="edit-lead-status" className="mb-1.5 block text-[13px] font-medium text-chalk-dim">
                  Status
                </label>
                <select
                  id="edit-lead-status"
                  value={status}
                  onChange={(e) => setStatus(e.target.value as LeadStatus)}
                  className="h-11 w-full rounded-lg border border-ink-700 bg-ink-950 px-3.5 text-[14px] text-chalk focus:border-signal focus:outline-none">

                  {STATUSES.map((s) =>
                  <option key={s} value={s}>{s}</option>
                  )}
                </select>
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
                  {isPending ? 'Saving…' : 'Save changes'}
                </Button>
              </div>
            </form>
          </motion.div>
        </div>
      }
    </AnimatePresence>);

}
