import React from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { ExternalLinkIcon, MapPinIcon, XIcon } from 'lucide-react';
import { Button } from '../ui/Button';
import type { LeadDTO } from '../../lib/api/leads';
import type { LeadStatus } from '../../types';

const STATUS_STYLES: Record<LeadStatus, string> = {
  New: 'border-signal/40 text-signal',
  Qualified: 'border-emerald-400/40 text-emerald-300',
  Contacted: 'border-amber-400/40 text-amber-300',
  Nurturing: 'border-chalk-faint/40 text-chalk-dim',
  Won: 'border-emerald-400/40 text-emerald-300',
  Lost: 'border-ember/40 text-ember'
};

interface Props {
  lead: LeadDTO | null;
  onClose: () => void;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="mb-1 text-[13px] font-medium text-chalk-dim">{label}</p>
      <div className="text-[14px] text-chalk">{children}</div>
    </div>
  );
}

// Read-only by design: leads here come from live discovery/CRM data, so this
// view exists to look leads up and act on them elsewhere (email/WhatsApp,
// delete) — not to hand-edit fields that a fresh search would just overwrite.
export function LeadDetailsModal({ lead, onClose }: Props) {
  return (
    <AnimatePresence>
      {lead &&
      <div className="fixed inset-0 z-[60] flex items-end justify-center p-0 sm:items-center sm:p-6">
          <motion.button
          type="button"
          aria-label="Close"
          onClick={onClose}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="absolute inset-0 bg-ink-950/85 backdrop-blur-sm" />

          <motion.div
          role="dialog"
          aria-modal="true"
          aria-labelledby="lead-details-title"
          initial={{ opacity: 0, y: 24, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 16, scale: 0.98 }}
          transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
          className="relative flex max-h-[88vh] w-full max-w-[480px] flex-col overflow-hidden rounded-t-2xl border border-ink-700 bg-ink-900 sm:rounded-2xl">

            <div className="flex items-start justify-between gap-4 border-b border-ink-850 px-6 py-5">
              <h2 id="lead-details-title" className="font-display text-[18px] font-semibold tracking-tight text-chalk">
                Lead details
              </h2>
              <button
              type="button"
              onClick={onClose}
              aria-label="Close dialog"
              className="rounded-lg p-1.5 text-chalk-faint hover:bg-ink-850 hover:text-chalk">

                <XIcon className="h-4 w-4" />
              </button>
            </div>

            <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-6 py-5 scrollbar-slim">
              <Field label="Full name">{lead.name}</Field>
              <Field label="Email">{lead.email || <span className="text-chalk-faint">Not available</span>}</Field>
              <Field label="Phone">{lead.phone || <span className="text-chalk-faint">Not available</span>}</Field>
              <Field label="Website">
                {lead.website ? (
                  <a
                    href={/^https?:\/\//.test(lead.website) ? lead.website : `https://${lead.website}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 text-signal hover:underline">
                    {lead.website}
                    <ExternalLinkIcon className="h-3 w-3" />
                  </a>
                ) : (
                  <span className="text-chalk-faint">Not available</span>
                )}
              </Field>
              <Field label="Address">
                {lead.address ? (
                  <a
                    href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(lead.address)}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 text-signal hover:underline">
                    {lead.address}
                    <MapPinIcon className="h-3 w-3 shrink-0" />
                  </a>
                ) : (
                  <span className="text-chalk-faint">Not available</span>
                )}
              </Field>
              <Field label="Industry">{lead.industry || <span className="text-chalk-faint">Not available</span>}</Field>
              {Object.keys(lead.social_links ?? {}).length > 0 &&
              <Field label="Social links">
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
                </Field>
              }
              <Field label="Status">
                <span
                  className={`inline-flex rounded-full border px-2.5 py-1 text-[12.5px] font-medium ${STATUS_STYLES[lead.status]}`}>
                  {lead.status}
                </span>
              </Field>
              {lead.score !== null &&
              <Field label="Score">{lead.score}/100</Field>
              }
              {lead.source &&
              <Field label="Source">{lead.source}</Field>
              }
            </div>

            <div className="flex justify-end gap-2 border-t border-ink-850 px-6 py-4">
              <Button type="button" variant="outline" onClick={onClose}>
                Close
              </Button>
            </div>
          </motion.div>
        </div>
      }
    </AnimatePresence>);

}
