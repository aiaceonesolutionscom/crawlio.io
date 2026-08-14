import React, { useCallback, useEffect, useState } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { GlobeIcon, Loader2Icon, UsersIcon, XIcon } from 'lucide-react';
import { cn } from '../../utils/cn';
import { ApiError } from '../../../lib/api/client';
import { listCrmEntries } from '../../../lib/api/crm';
import { getEligibleLeads, type EligibleLeadDTO } from '../../../lib/api/agent';

interface Props {
  open: boolean;
  onClose: () => void;
  /** multi = checkbox list (compose); single = click-to-pick (write AI) */
  mode: 'single' | 'multi';
  onSelect: (leads: EligibleLeadDTO[]) => void;
}

/**
 * Loads qualified CRM/agent leads — same source the Automation Builder uses
 * (CRM entries) plus email-ready eligible leads — and lets the user pick
 * recipients without leaving the compose / write-AI dialog.
 */
export function SelectCrmLeadsDialog({ open, onClose, mode, onSelect }: Props) {
  const { getToken } = useAuth();
  const [leads, setLeads] = useState<EligibleLeadDTO[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const fetchLeads = useCallback(async () => {
    if (!open) return;
    setLoading(true);
    setError(null);
    try {
      const token = await getToken();
      const [crmRes, eligibleRes] = await Promise.all([
        listCrmEntries(token),
        getEligibleLeads(token).catch(() => []),
      ]);
      const seen = new Set<string>();
      const merged: EligibleLeadDTO[] = [];
      for (const e of crmRes.items) {
        if (!e.lead.email) continue;
        if (seen.has(e.lead.email)) continue;
        seen.add(e.lead.email);
        merged.push({
          lead_id: e.lead.id,
          name: e.lead.name || e.lead.email,
          company: null,
          email: e.lead.email,
          website: e.lead.website,
          source: e.category === 'with_website' ? 'website' : 'non-website',
        });
      }
      for (const l of eligibleRes as EligibleLeadDTO[]) {
        if (!l.email || seen.has(l.email)) continue;
        seen.add(l.email);
        merged.push(l);
      }
      setLeads(merged);
      setSelected(new Set());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load CRM leads.');
      setLeads([]);
    } finally {
      setLoading(false);
    }
  }, [getToken, open]);

  useEffect(() => {
    fetchLeads();
    if (!open) setLeads([]);
  }, [fetchLeads, open]);

  if (!open) return null;

  const toggle = (id: string) => {
    if (mode === 'single') {
      const lead = leads.find((l) => l.lead_id === id);
      if (lead) onSelect([lead]);
      return;
    }
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div className="fixed inset-0 z-[70] flex items-end justify-center p-0 sm:items-center sm:p-6">
      <div className="absolute inset-0 bg-ink-950/85 backdrop-blur-sm" onClick={onClose} />
      <div className="relative flex max-h-[88vh] w-full max-w-[560px] flex-col overflow-hidden rounded-t-2xl border border-ink-700 bg-ink-900 sm:rounded-2xl">
        <div className="flex items-center justify-between border-b border-ink-850 px-6 py-4">
          <h3 className="flex items-center gap-2 font-display text-[16px] font-semibold text-chalk">
            <UsersIcon className="h-4 w-4 text-signal" />
            {mode === 'single' ? 'Select Lead from CRM' : 'Select Leads from CRM'}
          </h3>
          <button onClick={onClose} className="rounded-lg p-1 text-chalk-faint hover:bg-ink-850 hover:text-chalk">
            <XIcon className="h-4 w-4" />
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-4 scrollbar-slim">
          {loading && (
            <div className="flex items-center justify-center py-12">
              <Loader2Icon className="h-5 w-5 animate-spin text-chalk-faint" />
            </div>
          )}

          {error && (
            <div className="rounded-lg border border-ember/40 bg-ember/10 px-3 py-2 text-[12px] text-ember">{error}</div>
          )}

          {!loading && leads.length === 0 && !error && (
            <div className="py-10 text-center">
              <UsersIcon className="mx-auto h-7 w-7 text-chalk-faint" />
              <p className="mt-2 text-[12.5px] leading-relaxed text-chalk-dim">
                No leads with an email address yet. Add leads in Lead Center or qualify them with AI to make them
                appear here.
              </p>
            </div>
          )}

          {!loading && leads.length > 0 && (
            <div className="divide-y divide-ink-800/70 rounded-xl border border-ink-800">
              {leads.map((lead) => {
                const checked = selected.has(lead.lead_id);
                return (
                  <button
                    key={lead.lead_id}
                    type="button"
                    onClick={() => toggle(lead.lead_id)}
                    className={cn(
                      'flex w-full items-center gap-3 px-3.5 py-2.5 text-left hover:bg-ink-850/60',
                      mode === 'single' && 'cursor-pointer'
                    )}
                  >
                    {mode === 'multi' && (
                      <input
                        type="checkbox"
                        checked={checked}
                        readOnly
                        className="h-3.5 w-3.5 accent-[#6366f1]"
                      />
                    )}
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[13px] font-medium text-chalk">{lead.name}</p>
                      <p className="truncate text-[11.5px] text-chalk-dim">{lead.email}</p>
                      {lead.website && (
                        <p className="mt-0.5 flex items-center gap-1 truncate text-[11px] text-signal">
                          <GlobeIcon className="h-3 w-3 shrink-0" />
                          {lead.website.replace(/^https?:\/\//, '')}
                        </p>
                      )}
                    </div>
                    <span
                      className={cn(
                        'shrink-0 rounded-full border px-2 py-0.5 font-mono text-[9px] uppercase tracking-wide',
                        lead.source === 'website'
                          ? 'border-signal/40 text-signal'
                          : 'border-amber/40 text-amber'
                      )}
                    >
                      {lead.source === 'website' ? 'Website' : 'Non-Website'}
                    </span>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        <div className="flex items-center justify-between gap-3 border-t border-ink-850 px-5 py-3">
          {mode === 'multi' ? (
            <>
              <span className="truncate text-[11px] text-chalk-faint">
                {selected.size > 0 ? `${selected.size} selected` : ''}
              </span>
              <div className="flex gap-2">
                <button
                  onClick={onClose}
                  className="flex h-8 items-center rounded-lg border border-ink-700 bg-ink-850 px-3 text-[12px] text-chalk hover:border-ink-600"
                >
                  Cancel
                </button>
                <button
                  onClick={() => {
                    const picked = Array.from(selected)
                      .map((id) => leads.find((l) => l.lead_id === id))
                      .filter((l): l is EligibleLeadDTO => l !== undefined);
                    if (picked.length > 0) {
                      onSelect(picked);
                      setSelected(new Set());
                    }
                  }}
                  disabled={selected.size === 0}
                  className="flex h-8 items-center rounded-lg border border-signal/50 bg-signal/10 px-3 text-[12px] text-signal hover:bg-signal/20 disabled:opacity-50"
                >
                  Add Selected ({selected.size})
                </button>
              </div>
            </>
          ) : (
            <p className="text-[11px] text-chalk-faint">
              {leads.length > 0 ? 'Click a lead to fill the fields.' : ''}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}