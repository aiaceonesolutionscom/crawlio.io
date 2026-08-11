import React, { useCallback, useEffect, useState } from 'react';
import { useAuth } from '@clerk/clerk-react';
import {
  CheckIcon, EditIcon, Loader2Icon, SendIcon, SparklesIcon, UsersIcon, XIcon,
} from 'lucide-react';
import { cn } from '../utils/cn';
import { ApiError } from '../../lib/api/client';
import {
  approveOutreach, generateOutreach, getEligibleLeads, getOutreachUsage, regenerateOutreach,
  type EligibleLeadDTO, type OutreachDraftDTO, type OutreachUsageDTO,
} from '../../lib/api/agent';

export function OutreachTab() {
  const { getToken } = useAuth();
  const [usage, setUsage] = useState<OutreachUsageDTO | null>(null);
  const [leads, setLeads] = useState<EligibleLeadDTO[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [drafts, setDrafts] = useState<OutreachDraftDTO[]>([]);
  const [activeIdx, setActiveIdx] = useState(0);
  const [editing, setEditing] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [confirmSend, setConfirmSend] = useState(false);
  const [sending, setSending] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const token = await getToken();
      const [usageData, leadData] = await Promise.all([getOutreachUsage(token), getEligibleLeads(token)]);
      setUsage(usageData);
      setLeads(leadData);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load outreach data.');
    } finally {
      setLoading(false);
    }
  }, [getToken]);

  useEffect(() => {
    void fetchData();
  }, [fetchData]);

  useEffect(() => {
    if (usage && usage.remaining === 0) {
      setSelected(new Set());
    }
  }, [usage]);

  const toggleLead = (id: string) => {
    if (!usage || usage.remaining <= 0) return;
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (!usage || usage.remaining <= 0) return;
    setSelected((prev) => {
      if (prev.size === leads.length) return new Set();
      const copy = new Set(leads.slice(0, usage.remaining).map((lead) => lead.lead_id));
      return copy;
    });
  };

  const handleGenerate = async () => {
    if (selected.size === 0) return;
    setGenerating(true);
    setError(null);
    setMessage(null);
    try {
      const token = await getToken();
      const drafts = await generateOutreach(token, Array.from(selected));
      setDrafts(drafts);
      setActiveIdx(0);
      setEditing(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to generate outreach.');
    } finally {
      setGenerating(false);
    }
  };

  const handleRegenerate = async () => {
    const draft = drafts[activeIdx];
    if (!draft) return;
    setRegenerating(true);
    setError(null);
    try {
      const token = await getToken();
      const updated = await regenerateOutreach(token, draft.lead_id);
      setDrafts((prev) => prev.map((d, i) => (i === activeIdx ? updated : d)));
      setEditing(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to regenerate with Crawlio.');
    } finally {
      setRegenerating(false);
    }
  };

  const updateCurrentDraft = (patch: Partial<OutreachDraftDTO>) => {
    setDrafts((prev) => prev.map((d, i) => (i === activeIdx ? { ...d, ...patch } : d)));
  };

  const handleApprove = async () => {
    setSending(true);
    setError(null);
    try {
      const token = await getToken();
      const result = await approveOutreach(
        token,
        drafts.map((d) => ({ lead_id: d.lead_id, subject: d.subject, body: d.body })),
      );
      setConfirmSend(false);
      setDrafts([]);
      setMessage(`Sent: ${result.sent}, Skipped: ${result.rejected}`);
      const newSelected = new Set(selected);
      for (const r of result.results) {
        newSelected.delete(r.lead_id);
      }
      setSelected(newSelected);
      await fetchData();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to send outreach.');
    } finally {
      setSending(false);
    }
  };

  const activeDraft = drafts[activeIdx];
  const pct = usage && usage.limit > 0 ? Math.min(100, (usage.used / usage.limit) * 100) : 0;

  if (loading && leads.length === 0) {
    return (
      <div className="flex h-full items-center justify-center py-16">
        <Loader2Icon className="h-6 w-6 animate-spin text-chalk-faint" />
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-4">
      <div className="mb-4 grid gap-3 lg:grid-cols-[280px_1fr]">
        {/* Daily limit (top-left as requested) */}
        <div className="rounded-2xl border border-ink-800 bg-ink-900/90 p-4">
          <p className="text-[11px] font-medium uppercase tracking-wide text-chalk-dim">Daily Outreach</p>
          {usage && usage.limit > 0 ? (
            <>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="font-display text-[26px] font-semibold text-chalk">{usage.used}</span>
                <span className="text-[13px] text-chalk-dim">/ {usage.limit} used</span>
              </div>
              <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-ink-800">
                <div className="h-full rounded-full bg-signal" style={{ width: `${pct}%` }} />
              </div>
              <p className={cn('mt-2 text-[12px]', usage.remaining > 0 ? 'text-signal' : 'text-ember')}>
                {usage.remaining > 0 ? `${usage.remaining} remaining` : 'Daily limit reached for today.'}
              </p>
            </>
          ) : (
            <p className="mt-2 text-[12px] text-ember">This feature requires a Pro or Enterprise plan.</p>
          )}
        </div>

        {/* Eligible leads */}
        <div className="rounded-2xl border border-ink-800 bg-ink-900/90">
          <div className="flex items-center justify-between border-b border-ink-850 px-4 py-3">
            <p className="flex items-center gap-2 text-[13px] font-medium text-chalk">
              <UsersIcon className="h-4 w-4 text-signal" /> Eligible Leads
            </p>
            <div className="flex gap-2">
              <button
                onClick={toggleAll}
                disabled={!usage || usage.remaining <= 0}
                className="text-[11px] text-chalk-dim hover:text-chalk disabled:opacity-40"
              >
                Select all
              </button>
              <button
                onClick={handleGenerate}
                disabled={selected.size === 0 || generating || (usage ? usage.remaining <= 0 : false)}
                className="flex h-7 items-center gap-1 rounded-lg border border-signal/50 bg-signal/10 px-2.5 text-[11px] text-signal hover:bg-signal/20 disabled:opacity-40"
              >
                {generating ? <Loader2Icon className="h-3 w-3 animate-spin" /> : <SparklesIcon className="h-3 w-3" />}
                Generate Outreach
              </button>
            </div>
          </div>
          <div className="max-h-[260px] divide-y divide-ink-800/60 overflow-y-auto">
            {leads.length === 0 && !loading && (
              <div className="py-8 text-center">
                <p className="text-[12px] text-chalk-dim">
                  No eligible leads. Add leads with email addresses (or wait for discovery) to get started.
                </p>
              </div>
            )}
            {leads.map((lead) => {
              const checked = selected.has(lead.lead_id);
              return (
                <label key={lead.lead_id} className={cn('flex cursor-pointer items-center gap-2.5 px-4 py-2.5 hover:bg-ink-850/50', !usage?.remaining && 'opacity-50')}>
                  <input
                    type="checkbox"
                    checked={checked}
                    disabled={!usage?.remaining}
                    onChange={() => toggleLead(lead.lead_id)}
                    className="h-3.5 w-3.5 accent-[#6366f1]"
                  />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[12.5px] font-medium text-chalk">{lead.name}</p>
                    <p className="truncate text-[11px] text-chalk-dim">
                      {lead.email}
                      {lead.company ? ` · ${lead.company}` : ''}
                    </p>
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
                </label>
              );
            })}
          </div>
        </div>
      </div>

      {error && (
        <div className="mb-3 rounded-lg border border-ember/40 bg-ember/10 px-3 py-2 text-[12px] text-ember">{error}</div>
      )}
      {message && (
        <div className="mb-3 rounded-lg border border-signal/40 bg-signal/10 px-3 py-2 text-[12px] text-signal">{message}</div>
      )}

      {drafts.length > 0 && activeDraft && (
        <div className="rounded-2xl border border-ink-800 bg-ink-900/90 p-4">
          <div className="mb-3 flex items-center justify-between gap-2">
            <p className="text-[13px] font-medium text-chalk">Email Preview</p>
            <div className="flex flex-wrap gap-1">
              {drafts.map((d, i) => (
                <button
                  key={d.lead_id}
                  onClick={() => { setActiveIdx(i); setEditing(false); }}
                  className={cn(
                    'rounded-lg border px-2 py-1 text-[10px]',
                    i === activeIdx ? 'border-signal/50 bg-signal/10 text-signal' : 'border-ink-700 bg-ink-850 text-chalk-dim hover:border-ink-600'
                  )}
                >
                  {d.recipient_name || d.recipient_email}
                </button>
              ))}
            </div>
          </div>

          <div className="rounded-lg border border-ink-800 bg-ink-950 p-3">
            <p className="text-[10px] font-medium text-chalk-dim">To</p>
            <p className="text-[12.5px] text-chalk">{activeDraft.recipient_email}</p>
            <p className="mt-2 text-[10px] font-medium text-chalk-dim">Subject</p>
            {editing ? (
              <input
                value={activeDraft.subject}
                onChange={(e) => updateCurrentDraft({ subject: e.target.value })}
                className="mt-0.5 h-8 w-full rounded-lg border border-ink-700 bg-ink-900 px-2 text-[12.5px] text-chalk focus:border-signal focus:outline-none"
              />
            ) : (
              <p className="text-[12.5px] font-medium text-chalk">{activeDraft.subject}</p>
            )}
            <p className="mt-2 text-[10px] font-medium text-chalk-dim">Body</p>
            {editing ? (
              <textarea
                value={activeDraft.body}
                onChange={(e) => updateCurrentDraft({ body: e.target.value })}
                rows={9}
                className="mt-0.5 w-full rounded-lg border border-ink-700 bg-ink-900 px-2 py-1.5 text-[12.5px] leading-relaxed text-chalk focus:border-signal focus:outline-none"
              />
            ) : (
              <div className="mt-0.5 whitespace-pre-wrap text-[12.5px] leading-relaxed text-chalk-dim">{activeDraft.body}</div>
            )}
          </div>

          <div className="mt-3 flex flex-wrap justify-end gap-2">
            <button
              onClick={() => setEditing((v) => !v)}
              className="flex h-8 items-center gap-1 rounded-lg border border-ink-700 bg-ink-850 px-3 text-[11px] text-chalk hover:border-ink-600"
            >
              <EditIcon className="h-3.5 w-3.5" /> {editing ? 'Done Editing' : 'Edit'}
            </button>
            <button
              onClick={handleRegenerate}
              disabled={regenerating}
              className="flex h-8 items-center gap-1 rounded-lg border border-signal/50 bg-signal/10 px-3 text-[11px] text-signal hover:bg-signal/20 disabled:opacity-40"
            >
              {regenerating ? <Loader2Icon className="h-3.5 w-3.5 animate-spin" /> : <SparklesIcon className="h-3.5 w-3.5" />}
              Change with Crawlio
            </button>
            <button
              onClick={() => setConfirmSend(true)}
              disabled={sending || (usage ? usage.remaining <= 0 : false)}
              className="flex h-8 items-center gap-1 rounded-lg border border-emerald/50 bg-emerald/10 px-3 text-[11px] text-emerald hover:bg-emerald/20 disabled:opacity-40"
            >
              <SendIcon className="h-3.5 w-3.5" /> Approve & Send
            </button>
          </div>
        </div>
      )}

      {confirmSend && (
        <div className="fixed inset-0 z-[90] flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-ink-950/80" onClick={() => !sending && setConfirmSend(false)} />
          <div className="relative w-full max-w-md rounded-2xl border border-ink-700 bg-ink-900 p-5">
            <div className="flex items-start justify-between gap-3">
              <h3 className="text-[15px] font-semibold text-chalk">Send {drafts.length} outreach emails?</h3>
              <button onClick={() => !sending && setConfirmSend(false)} className="text-chalk-faint hover:text-chalk">
                <XIcon className="h-4 w-4" />
              </button>
            </div>
            <p className="mt-2 text-[12.5px] leading-relaxed text-chalk-dim">
              Each email is personalized and will be sent from your connected email account. Recipients who were
              already contacted or who unsubscribed will be skipped automatically.
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <button
                onClick={() => setConfirmSend(false)}
                disabled={sending}
                className="flex h-8 items-center rounded-lg border border-ink-700 bg-ink-850 px-3 text-[11px] text-chalk hover:border-ink-600"
              >
                Cancel
              </button>
              <button
                onClick={handleApprove}
                disabled={sending}
                className="flex h-8 items-center gap-1 rounded-lg border border-emerald/50 bg-emerald/10 px-3 text-[11px] text-emerald hover:bg-emerald/20 disabled:opacity-40"
              >
                {sending ? <Loader2Icon className="h-3.5 w-3.5 animate-spin" /> : <CheckIcon className="h-3.5 w-3.5" />}
                {sending ? 'Sending...' : 'Approve & Send'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}