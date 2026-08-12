import React, { useCallback, useEffect, useState } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { BrainCircuitIcon, CalendarIcon, CheckCircleIcon, Loader2Icon, UserIcon, XIcon } from 'lucide-react';
import { cn } from '../utils/cn';
import { ApiError } from '../../lib/api/client';
import { getEligibleLeads, listMeetings, type EligibleLeadDTO, type MeetingDTO } from '../../lib/api/agent';

type PipelineFilter = 'all' | 'website' | 'non-website' | 'hot';

export function CrmTab() {
  const { getToken } = useAuth();
  const [leads, setLeads] = useState<EligibleLeadDTO[]>([]);
  const [meetings, setMeetings] = useState<MeetingDTO[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<PipelineFilter>('all');
  const [selectedLead, setSelectedLead] = useState<EligibleLeadDTO | null>(null);
  const [visibleMeetings, setVisibleMeetings] = useState(8);
  const [visibleLeads, setVisibleLeads] = useState(25);

  const hotIds = new Set(
    meetings
      .filter((m) => m.lead_email)
      .map((m) => m.lead_email as string)
  );

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const token = await getToken();
      const [leadData, meetingData] = await Promise.all([getEligibleLeads(token), listMeetings(token)]);
      setLeads(leadData);
      setMeetings(meetingData);
      setVisibleLeads(25);
      setVisibleMeetings(8);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load CRM data.');
    } finally {
      setLoading(false);
    }
  }, [getToken]);

  useEffect(() => {
    void fetchData();
  }, [fetchData]);

  const filtered = leads.filter((lead) => {
    if (filter === 'all') return true;
    if (filter === 'website') return lead.source === 'website';
    if (filter === 'non-website') return lead.source !== 'website';
    if (filter === 'hot') return lead.email ? hotIds.has(lead.email) : false;
    return true;
  });

  const selectedMeeting = selectedLead?.email ? meetings.find((m) => m.lead_email === selectedLead.email) : undefined;

  if (loading && leads.length === 0 && meetings.length === 0) {
    return (
      <div className="flex h-full items-center justify-center py-16">
        <Loader2Icon className="h-6 w-6 animate-spin text-chalk-faint" />
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-4">
      {error && (
        <div className="mb-3 rounded-lg border border-ember/40 bg-ember/10 px-3 py-2 text-[12px] text-ember">{error}</div>
      )}

      {/* Booked meetings */}
      <div className="mb-4 rounded-2xl border border-ink-800 bg-ink-900/90 p-4">
        <p className="flex items-center gap-2 text-[13px] font-medium text-chalk">
          <CalendarIcon className="h-4 w-4 text-signal" /> Booked Meetings
        </p>
        {meetings.length === 0 ? (
          <p className="mt-2 text-[12px] text-chalk-dim">
            No meetings yet. When the AI agent detects interest and books a call, it appears here.
          </p>
        ) : (
          <div className="mt-3 grid gap-2 lg:grid-cols-2">
            {meetings.slice(0, visibleMeetings).map((meeting) => (
              <div key={meeting.id} className="rounded-lg border border-ink-800 bg-ink-850 p-2.5">
                <div className="flex items-center justify-between gap-2">
                  <p className="truncate text-[12.5px] font-medium text-chalk">
                    <UserIcon className="mr-1 inline h-3.5 w-3.5 text-signal" />
                    {meeting.lead_name || meeting.lead_email || 'Anonymous lead'}
                  </p>
                  <span className="rounded-full border border-ink-700 bg-ink-900 px-2 py-0.5 font-mono text-[9px] uppercase tracking-wide text-chalk-dim">
                    {meeting.status}
                  </span>
                </div>
                <p className="truncate text-[11px] text-chalk-dim">{meeting.lead_email}</p>
                <p className="mt-1 text-[11px] text-chalk">
                  {meeting.scheduled_at ? new Date(meeting.scheduled_at).toLocaleString() : 'Time TBD'}
                </p>
                <p className="text-[10px] font-mono text-chalk-faint">Ref: {meeting.booking_ref}</p>
              </div>
            ))}
          </div>
        )}
        {meetings.length > visibleMeetings && (
          <button
            onClick={() => setVisibleMeetings((v) => v + 10)}
            className="mt-3 w-full rounded-lg border border-ink-700 bg-ink-850 py-1.5 text-[11px] text-chalk-dim hover:border-ink-600 hover:text-chalk"
          >
            Load more meetings ({meetings.length - visibleMeetings} remaining)
          </button>
        )}
      </div>

      {/* Pipeline */}
      <div className="rounded-2xl border border-ink-800 bg-ink-900/90">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-ink-850 px-4 py-3">
          <p className="flex items-center gap-2 text-[13px] font-medium text-chalk">
            <BrainCircuitIcon className="h-4 w-4 text-signal" /> Agent Pipeline
          </p>
          <div className="flex flex-wrap gap-1">
            {(
              [
                { id: 'all' as const, label: 'All' },
                { id: 'hot' as const, label: 'Hot' },
                { id: 'website' as const, label: 'Website' },
                { id: 'non-website' as const, label: 'Non-Website' },
              ]
            ).map((f) => (
              <button
                key={f.id}
                onClick={() => setFilter(f.id)}
                className={cn(
                  'rounded-lg border px-2 py-1 text-[10px]',
                  filter === f.id
                    ? 'border-signal/50 bg-signal/10 text-signal'
                    : 'border-ink-700 bg-ink-850 text-chalk-dim hover:border-ink-600'
                )}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        <div className="divide-y divide-ink-800/60">
          {filtered.length === 0 && (
            <div className="py-10 text-center">
              <p className="text-[12px] text-chalk-dim">
                {filter === 'hot'
                  ? 'No hot leads with booked meetings yet.'
                  : 'No leads in this pipeline yet. Import leads or run discovery to see them here.'}
              </p>
            </div>
          )}
          {filtered.slice(0, visibleLeads).map((lead) => {
            const hot = lead.email ? hotIds.has(lead.email) : false;
            return (
              <div
                key={lead.lead_id}
                onClick={() => setSelectedLead(lead)}
                className="flex cursor-pointer items-center gap-3 px-4 py-2.5 hover:bg-ink-850/50"
              >
                <span
                  className={cn(
                    'h-2 w-2 shrink-0 rounded-full',
                    hot ? 'bg-emerald animate-pulse' : lead.source === 'website' ? 'bg-signal' : 'bg-amber'
                  )}
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
                    'shrink-0 rounded-full border px-2 py-0.5 text-[9px] uppercase tracking-wide',
                    hot
                      ? 'border-emerald/40 text-emerald'
                      : lead.source === 'website'
                      ? 'border-signal/40 text-signal'
                      : 'border-amber/40 text-amber'
                  )}
                >
                  {hot ? 'Hot' : lead.source === 'website' ? 'Website' : 'Non-Website'}
                </span>
              </div>
            );
          })}
        </div>
        {filtered.length > visibleLeads && (
          <div className="border-t border-ink-800/60 p-2">
            <button
              onClick={() => setVisibleLeads((v) => v + 25)}
              className="w-full rounded-lg border border-ink-700 bg-ink-850 py-1.5 text-[11px] text-chalk-dim hover:border-ink-600 hover:text-chalk"
            >
              Load more leads ({filtered.length - visibleLeads} remaining)
            </button>
          </div>
        )}
      </div>

      {selectedLead && (
        <div className="fixed inset-0 z-[90] flex items-end justify-center p-4 sm:items-center">
          <div className="absolute inset-0 bg-ink-950/80" onClick={() => setSelectedLead(null)} />
          <div className="relative w-full max-w-lg rounded-2xl border border-ink-700 bg-ink-900 p-5">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <h3 className="text-[15px] font-semibold text-chalk">{selectedLead.name}</h3>
                <p className="truncate text-[12px] text-chalk-dim">{selectedLead.email}</p>
              </div>
              <button onClick={() => setSelectedLead(null)} className="text-chalk-faint hover:text-chalk">
                <XIcon className="h-4 w-4" />
              </button>
            </div>

            <div className="mt-3 space-y-2 rounded-lg border border-ink-800 bg-ink-950 p-3">
              <p className="text-[10px] font-medium uppercase tracking-wide text-chalk-faint">Lead Details</p>
              <div className="grid grid-cols-2 gap-2 text-[12px]">
                <div>
                  <p className="text-chalk-faint">Company</p>
                  <p className="text-chalk">{selectedLead.company || '—'}</p>
                </div>
                <div>
                  <p className="text-chalk-faint">Website</p>
                  <p className="truncate text-chalk">{selectedLead.website || '—'}</p>
                </div>
                <div>
                  <p className="text-chalk-faint">Source</p>
                  <p className="text-chalk">{selectedLead.source}</p>
                </div>
                <div>
                  <p className="text-chalk-faint">Stage</p>
                  <p className={cn('font-medium', selectedMeeting ? 'text-emerald' : 'text-chalk')}>
                    {selectedMeeting ? 'Meeting booked' : 'Awaiting reply'}
                  </p>
                </div>
              </div>
            </div>

            <div className="mt-3 space-y-2 rounded-lg border border-ink-800 bg-ink-950 p-3">
              <p className="text-[10px] font-medium uppercase tracking-wide text-chalk-faint">AI Agent Status</p>
              <p className="flex items-start gap-2 text-[12.5px] leading-relaxed text-chalk-dim">
                <CheckCircleIcon className="mt-0.5 h-4 w-4 shrink-0 text-signal" />
                This lead is enrolled with the agent. On inbound email, the agent loads your business knowledge,
                identifies intent and drafts a reply for your approval before sending.
              </p>
              {selectedMeeting ? (
                <div className="flex items-center gap-2 rounded-lg border border-emerald/30 bg-emerald/5 px-2.5 py-2 text-[12px] text-emerald">
                  <CalendarIcon className="h-3.5 w-3.5" />
                  {selectedMeeting.lead_name || selectedLead.name} &middot; {selectedMeeting.scheduled_at ? new Date(selectedMeeting.scheduled_at).toLocaleString() : 'TBD'}
                </div>
              ) : (
                <p className="text-[11.5px] text-chalk-faint">
                  No meeting yet — the agent will offer a booking slot when it detects strong interest.
                </p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}