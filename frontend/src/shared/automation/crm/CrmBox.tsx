import React, { useEffect, useState } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { ChevronLeftIcon, ChevronRightIcon, DownloadIcon, GlobeIcon, UsersIcon } from 'lucide-react';
import { listCrmEntries, type CrmEntryDTO } from '../../../lib/api/crm';
import { LeadDetailsModal } from '../../leads/LeadDetailsModal';
import { Button } from '../../ui/Button';
import type { LeadDTO } from '../../../lib/api/leads';

const CSV_COLUMNS = [
  'name', 'email', 'phone', 'website', 'address', 'industry', 'score', 'category', 'added_at'
] as const;

// CSV must quote any field containing a comma, quote, or newline, and double
// up internal quotes — plain string interpolation silently corrupts the file
// the moment a lead's name/address contains a comma (extremely common).
function csvCell(value: string | number | null): string {
  const s = value === null || value === undefined ? '' : String(value);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function entriesToCsv(entries: CrmEntryDTO[]): string {
  const rows = entries.map((entry) => {
    const values: Record<(typeof CSV_COLUMNS)[number], string | number | null> = {
      name: entry.lead.name,
      email: entry.lead.email,
      phone: entry.lead.phone,
      website: entry.lead.website,
      address: entry.lead.address,
      industry: entry.lead.industry,
      score: entry.lead.score,
      category: entry.category === 'with_website' ? 'With website' : 'No website',
      added_at: entry.added_at
    };
    return CSV_COLUMNS.map((col) => csvCell(values[col])).join(',');
  });
  return [CSV_COLUMNS.join(','), ...rows].join('\r\n');
}

const CRM_PAGE_SIZE = 25;

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
  const [page, setPage] = useState(1);
  const totalPages = Math.max(1, Math.ceil(entries.length / CRM_PAGE_SIZE));
  const clampedPage = Math.min(page, totalPages);
  const pageEntries = entries.slice((clampedPage - 1) * CRM_PAGE_SIZE, clampedPage * CRM_PAGE_SIZE);

  return (
    <div className="flex-1 overflow-hidden rounded-xl border border-ink-800">
      <div className="flex items-center justify-between border-b border-ink-800 bg-ink-850/60 px-4 py-2.5">
        <p className="text-[12.5px] font-medium text-chalk-dim">{title}</p>
        <span className="font-mono text-[11px] text-chalk-faint">{entries.length}</span>
      </div>
      {entries.length === 0 ? (
        <p className="px-4 py-8 text-center text-[13px] text-chalk-faint">{emptyText}</p>
      ) : (
        <>
          <ul className="max-h-80 divide-y divide-ink-850 overflow-y-auto scrollbar-slim">
            {pageEntries.map((entry) => (
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
          {totalPages > 1 && (
            <div className="flex items-center justify-between border-t border-ink-850 bg-ink-850/40 px-3 py-2">
              <button
                type="button"
                disabled={clampedPage <= 1}
                onClick={() => setPage(clampedPage - 1)}
                className="flex items-center gap-1 rounded-md px-2 py-1 text-[11.5px] text-chalk-dim hover:bg-ink-800 disabled:cursor-not-allowed disabled:opacity-40"
              >
                <ChevronLeftIcon className="h-3.5 w-3.5" />
                Prev
              </button>
              <span className="font-mono text-[11px] text-chalk-faint">
                Page {clampedPage} of {totalPages}
              </span>
              <button
                type="button"
                disabled={clampedPage >= totalPages}
                onClick={() => setPage(clampedPage + 1)}
                className="flex items-center gap-1 rounded-md px-2 py-1 text-[11.5px] text-chalk-dim hover:bg-ink-800 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Next
                <ChevronRightIcon className="h-3.5 w-3.5" />
              </button>
            </div>
          )}
        </>
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

  const handleDownloadCsv = () => {
    const blob = new Blob([entriesToCsv(entries)], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = 'crm-leads.csv';
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="mb-6 rounded-2xl border border-ink-800 bg-ink-900 p-6">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <UsersIcon className="h-4 w-4 text-signal" aria-hidden="true" />
          <p className="font-display text-[16px] font-semibold tracking-tight text-chalk">CRM</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="font-mono text-[11px] uppercase tracking-wider text-chalk-faint">
            {entries.length} qualified lead{entries.length === 1 ? '' : 's'}
          </span>
          {entries.length > 0 && (
            <Button size="sm" variant="outline" onClick={handleDownloadCsv}>
              <DownloadIcon className="h-3.5 w-3.5" />
              Download CSV
            </Button>
          )}
        </div>
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

      <LeadDetailsModal lead={selectedLead} onClose={() => setSelectedLead(null)} />
    </div>
  );
}
