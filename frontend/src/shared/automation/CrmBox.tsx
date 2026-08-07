import React, { useEffect, useState } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { GlobeIcon, UsersIcon } from 'lucide-react';
import { listCrmEntries, type CrmEntryDTO } from '../../lib/api/crm';
import { EditLeadModal } from '../leads/EditLeadModal';
import type { LeadDTO } from '../../lib/api/leads';

function CrmColumn({
  title,
  entries,
  emptyText,
  onSelect
}: {
  title: string;
  entries: CrmEntryDTO[];
  emptyText: string;
  onSelect: (lead: LeadDTO) => void;
}) {
  return (
    <div className="flex-1 overflow-hidden rounded-xl border border-ink-800">
      <div className="flex items-center justify-between border-b border-ink-800 bg-ink-850/60 px-4 py-2.5">
        <p className="text-[12.5px] font-medium text-chalk-dim">{title}</p>
        <span className="font-mono text-[11px] text-chalk-faint">{entries.length}</span>
      </div>
      {entries.length === 0 ? (
        <p className="px-4 py-8 text-center text-[13px] text-chalk-faint">{emptyText}</p>
      ) : (
        <ul className="max-h-80 divide-y divide-ink-850 overflow-y-auto scrollbar-slim">
          {entries.map((entry) => (
            <li key={entry.id}>
              <button
                type="button"
                onClick={() => onSelect(entry.lead)}
                className="block w-full px-4 py-3 text-left hover:bg-ink-850/60"
              >
                <p className="truncate text-[13.5px] font-medium text-chalk">{entry.lead.name}</p>
                <p className="mt-0.5 truncate text-[12px] text-chalk-faint">
                  {[entry.lead.email, entry.lead.phone].filter(Boolean).join(' · ') || 'No contact details'}
                </p>
                <div className="mt-1.5 flex items-center justify-between">
                  {entry.lead.website ? (
                    <span className="flex items-center gap-1 truncate text-[11.5px] text-signal">
                      <GlobeIcon className="h-3 w-3 shrink-0" />
                      {entry.lead.website.replace(/^https?:\/\//, '')}
                    </span>
                  ) : (
                    <span className="text-[11.5px] text-chalk-faint">No website</span>
                  )}
                  <span className="font-mono text-[11px] text-chalk-dim">
                    {entry.lead.score !== null ? `${entry.lead.score}/100` : '—'}
                  </span>
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function CrmBox() {
  const { getToken } = useAuth();
  const [entries, setEntries] = useState<CrmEntryDTO[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedLead, setSelectedLead] = useState<LeadDTO | null>(null);

  const refresh = async () => {
    setIsLoading(true);
    const token = await getToken();
    const res = await listCrmEntries(token);
    setEntries(res.items);
    setIsLoading(false);
  };

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [getToken]);

  const withWebsite = entries.filter((e) => e.category === 'with_website');
  const withoutWebsite = entries.filter((e) => e.category === 'no_website');

  return (
    <div className="mb-6 rounded-2xl border border-ink-800 bg-ink-900 p-6">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <UsersIcon className="h-4 w-4 text-signal" aria-hidden="true" />
          <p className="font-display text-[16px] font-semibold tracking-tight text-chalk">CRM</p>
        </div>
        <span className="font-mono text-[11px] uppercase tracking-wider text-chalk-faint">
          {entries.length} qualified lead{entries.length === 1 ? '' : 's'}
        </span>
      </div>

      {isLoading && <p className="mt-5 text-[14px] text-chalk-dim">Loading…</p>}

      {!isLoading && entries.length === 0 && (
        <div className="mt-5 rounded-xl border border-dashed border-ink-800 p-8 text-center">
          <UsersIcon className="mx-auto h-6 w-6 text-chalk-faint" aria-hidden="true" />
          <p className="mt-3 text-[14px] text-chalk-dim">
            No leads in your CRM yet. Go to Lead Center → &ldquo;Filter your leads with AI&rdquo; and add your best
            leads here.
          </p>
        </div>
      )}

      {!isLoading && entries.length > 0 && (
        <div className="mt-5 flex flex-col gap-3 sm:flex-row">
          <CrmColumn
            title="With website leads"
            entries={withWebsite}
            emptyText="No qualified leads with a website yet."
            onSelect={setSelectedLead}
          />
          <CrmColumn
            title="Non website leads"
            entries={withoutWebsite}
            emptyText="No qualified leads without a website."
            onSelect={setSelectedLead}
          />
        </div>
      )}

      <EditLeadModal
        lead={selectedLead}
        onClose={() => setSelectedLead(null)}
        onUpdated={() => void refresh()}
      />
    </div>
  );
}
