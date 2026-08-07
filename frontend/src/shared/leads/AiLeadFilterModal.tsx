import React, { useEffect, useState } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { AnimatePresence, motion } from 'framer-motion';
import { CheckIcon, GlobeIcon, Loader2Icon, SparklesIcon, XIcon } from 'lucide-react';
import { Button } from '../ui/Button';
import { cn } from '../utils/cn';
import { aiFilterLeads, addToCrm, type AiFilterResponseDTO } from '../../lib/api/crm';
import type { LeadDTO } from '../../lib/api/leads';
import { ApiError } from '../../lib/api/client';

interface Props {
  open: boolean;
  onClose: () => void;
}

export function AiLeadFilterModal({ open, onClose }: Props) {
  const { getToken } = useAuth();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<AiFilterResponseDTO | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [isAdding, setIsAdding] = useState(false);
  const [addSummary, setAddSummary] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setError(null);
    setAddSummary(null);
    setIsLoading(true);
    (async () => {
      try {
        const token = await getToken();
        const res = await aiFilterLeads(token);
        setData(res);
        setSelected(new Set([...res.with_website, ...res.without_website].map((l) => l.id)));
      } catch (err) {
        setError(err instanceof ApiError ? err.message : 'Could not run the AI filter. Please try again.');
      } finally {
        setIsLoading(false);
      }
    })();
  }, [open, getToken]);

  const handleClose = () => {
    setData(null);
    setSelected(new Set());
    setAddSummary(null);
    onClose();
  };

  const toggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleAddToCrm = async () => {
    const ids = Array.from(selected);
    if (ids.length === 0) return;
    setIsAdding(true);
    setError(null);
    try {
      const token = await getToken();
      const res = await addToCrm(token, ids);
      setAddSummary(
        `${res.added} lead${res.added === 1 ? '' : 's'} added to CRM` +
          (res.skipped ? `, ${res.skipped} already there` : '')
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not add to CRM. Please try again.');
    } finally {
      setIsAdding(false);
    }
  };

  const renderColumn = (title: string, leads: LeadDTO[], emptyText: string, showRating: boolean) => (
    <div className="flex-1 overflow-hidden rounded-xl border border-ink-800">
      <div className="border-b border-ink-800 bg-ink-850/60 px-4 py-2.5">
        <p className="text-[12.5px] font-medium text-chalk-dim">
          {title} <span className="text-chalk-faint">· {leads.length}</span>
        </p>
      </div>
      {leads.length === 0 ? (
        <p className="px-4 py-8 text-center text-[13px] text-chalk-faint">{emptyText}</p>
      ) : (
        <ul className="max-h-96 divide-y divide-ink-850 overflow-y-auto scrollbar-slim">
          {leads.map((lead) => (
            <li key={lead.id} className="flex items-start gap-3 px-4 py-3">
              <button
                type="button"
                onClick={() => toggle(lead.id)}
                aria-pressed={selected.has(lead.id)}
                className={cn(
                  'mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border',
                  selected.has(lead.id) ? 'border-signal bg-signal text-signal-deep' : 'border-ink-600'
                )}
              >
                {selected.has(lead.id) && <CheckIcon className="h-3 w-3" />}
              </button>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <p className="truncate text-[13.5px] font-medium text-chalk">{lead.name}</p>
                  {lead.industry && (
                    <span className="shrink-0 rounded-full border border-ink-700 px-2 py-0.5 text-[10.5px] text-chalk-faint">
                      {lead.industry}
                    </span>
                  )}
                </div>
                <p className="truncate text-[12px] text-chalk-faint">
                  {[lead.email, lead.phone].filter(Boolean).join(' · ') || 'No contact details'}
                </p>
                {showRating && lead.website && (
                  <a
                    href={lead.website}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-0.5 flex items-center gap-1 truncate text-[12px] text-signal hover:underline"
                  >
                    <GlobeIcon className="h-3 w-3 shrink-0" />
                    {lead.website.replace(/^https?:\/\//, '')}
                  </a>
                )}
                {Object.keys(lead.social_links ?? {}).length > 0 && (
                  <div className="mt-0.5 flex flex-wrap gap-x-2">
                    {Object.keys(lead.social_links).map((platform) => (
                      <span key={platform} className="text-[11px] capitalize text-chalk-faint">
                        {platform}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              <span className="shrink-0 font-mono text-[12px] text-chalk-dim">
                {lead.scoring_failed ? (
                  <span className="text-ember">Failed</span>
                ) : lead.score !== null ? (
                  `${lead.score}/100`
                ) : (
                  <span className="text-chalk-faint">Scoring…</span>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-[60] flex items-end justify-center p-0 sm:items-center sm:p-6">
          <motion.button
            type="button"
            aria-label="Close"
            onClick={handleClose}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 bg-ink-950/85 backdrop-blur-sm"
          />

          <motion.div
            role="dialog"
            aria-modal="true"
            aria-labelledby="ai-filter-title"
            initial={{ opacity: 0, y: 24, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.98 }}
            transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
            className="relative flex max-h-[88vh] w-full max-w-[880px] flex-col overflow-hidden rounded-t-2xl border border-ink-700 bg-ink-900 sm:rounded-2xl"
          >
            <div className="flex items-start justify-between gap-4 border-b border-ink-850 px-6 py-5">
              <div>
                <h2
                  id="ai-filter-title"
                  className="flex items-center gap-2 font-display text-[18px] font-semibold tracking-tight text-chalk"
                >
                  <SparklesIcon className="h-4 w-4 text-signal" />
                  Filter your leads with AI
                </h2>
                <p className="mt-1 text-[13px] text-chalk-dim">
                  Every lead in this workspace, split by whether it has a website, ranked by AI score.
                </p>
              </div>
              <button
                type="button"
                onClick={handleClose}
                aria-label="Close dialog"
                className="rounded-lg p-1.5 text-chalk-faint hover:bg-ink-850 hover:text-chalk"
              >
                <XIcon className="h-4 w-4" />
              </button>
            </div>

            <div className="flex flex-1 flex-col gap-4 overflow-y-auto px-6 py-5 scrollbar-slim">
              {isLoading && (
                <div className="flex flex-1 items-center justify-center py-16">
                  <Loader2Icon className="h-5 w-5 animate-spin text-chalk-faint" />
                </div>
              )}

              {error && (
                <p role="alert" className="rounded-lg border border-ember/40 bg-ember/10 px-3.5 py-2.5 text-[13px] text-ember">
                  {error}
                </p>
              )}

              {addSummary && (
                <p className="rounded-lg border border-signal/40 bg-signal/10 px-3.5 py-2.5 text-[13px] text-signal">
                  {addSummary}
                </p>
              )}

              {!isLoading && data && (
                <div className="flex flex-col gap-4 sm:flex-row">
                  {renderColumn('Has a website', data.with_website, 'No leads with a website yet.', true)}
                  {renderColumn('No website', data.without_website, 'No leads without a website.', false)}
                </div>
              )}
            </div>

            <div className="flex items-center justify-between gap-2 border-t border-ink-850 px-6 py-4">
              <p className="text-[12px] text-chalk-faint">{selected.size} selected</p>
              <div className="flex gap-2">
                <Button type="button" variant="outline" onClick={handleClose}>
                  Close
                </Button>
                <Button type="button" disabled={selected.size === 0 || isAdding} onClick={() => void handleAddToCrm()}>
                  {isAdding && <Loader2Icon className="h-4 w-4 animate-spin" />}
                  {isAdding ? 'Adding…' : 'Add this data into CRM'}
                </Button>
              </div>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
