import React, { useCallback, useEffect, useState } from 'react';
import { useAuth } from '@clerk/clerk-react';
import {
  AlertCircleIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  CompassIcon,
  DownloadIcon,
  MailIcon,
  MessageSquareIcon,
  PencilIcon,
  PlusIcon,
  RefreshCwIcon,
  SearchIcon,
  SparklesIcon,
  Trash2Icon,
  WandSparklesIcon
} from 'lucide-react';
import { PageHeader } from '../layout/PageHeader';
import { Button } from '../ui/Button';
import { useSession } from '../../contexts/SessionContext';
import {
  deleteAllLeads,
  deleteLead,
  enrichLeads,
  exportLeads,
  listLeads,
  sendLeadEmail,
  sendLeadWhatsApp,
  type LeadDTO
} from '../../lib/api/leads';
import { ApiError } from '../../lib/api/client';
import { cn } from '../utils/cn';
import { AddLeadModal } from './AddLeadModal';
import { EditLeadModal } from './EditLeadModal';
import { LeadDiscoveryModal } from './LeadDiscoveryModal';
import { AiLeadFilterModal } from './AiLeadFilterModal';
import type { LeadStatus } from '../../types';

const STATUS_STYLES: Record<LeadStatus, string> = {
  New: 'border-ink-600 text-chalk-dim',
  Qualified: 'border-signal/50 text-signal',
  Contacted: 'border-sky-soft/50 text-sky-soft',
  Nurturing: 'border-ember/40 text-ember',
  Won: 'border-signal text-signal',
  Lost: 'border-ink-700 text-chalk-faint'
};

const PAGE_SIZE = 20;

export interface LeadCenterConfig {
  tier: 'free' | 'pro' | 'enterprise';
  pageLimit?: number;
  searchEnabled?: boolean;
  whatsappEnabled?: boolean;
  bulkExportEnabled?: boolean;
  discoveryCap?: number;
  discoveryEnhanced?: boolean;
  aiFilterEnabled?: boolean;
  onUpgrade?: () => void;
}

export function LeadCenterPage({
  tier,
  pageLimit = PAGE_SIZE,
  searchEnabled = true,
  whatsappEnabled = true,
  bulkExportEnabled = false,
  discoveryCap = 50,
  discoveryEnhanced = false,
  aiFilterEnabled = false,
  onUpgrade
}: LeadCenterConfig) {
  const { user } = useSession();
  const { getToken } = useAuth();
  const [leads, setLeads] = useState<LeadDTO[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [query, setQuery] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [discoverOpen, setDiscoverOpen] = useState(false);
  const [aiFilterOpen, setAiFilterOpen] = useState(false);
  const [editLead, setEditLead] = useState<LeadDTO | null>(null);
  const [busyLeadId, setBusyLeadId] = useState<string | null>(null);
  const [isExporting, setIsExporting] = useState(false);
  const [isDeletingAll, setIsDeletingAll] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [isDeletingSelected, setIsDeletingSelected] = useState(false);
  const [isEnriching, setIsEnriching] = useState(false);
  const [enrichSummary, setEnrichSummary] = useState<string | null>(null);

  const refresh = useCallback(
    async (search?: string, pageNum = page) => {
      setIsLoading(true);
      setLoadError(null);
      try {
        const token = await getToken();
        const res = await listLeads(token, {
          search: searchEnabled ? search : undefined,
          page: pageNum,
          limit: pageLimit
        });
        const maxPage = Math.max(1, Math.ceil(res.total / pageLimit));
        if (res.total > 0 && pageNum > maxPage) {
          // Deleting leads (single/bulk/all) can leave the current page past
          // the new last page — refetch the last valid page instead of
          // showing an empty/stale one.
          const retry = await listLeads(token, {
            search: searchEnabled ? search : undefined,
            page: maxPage,
            limit: pageLimit
          });
          setLeads(retry.items);
          setTotal(retry.total);
          setPage(retry.page);
          setSelectedIds(new Set());
          return;
        }
        setLeads(res.items);
        setTotal(res.total);
        setPage(res.page);
        setSelectedIds(new Set());
      } catch (err) {
        setLoadError(err instanceof ApiError ? err.message : 'Failed to load leads. Please try again.');
      } finally {
        setIsLoading(false);
      }
    },
    [getToken, page, pageLimit, searchEnabled]
  );

  useEffect(() => {
    void refresh(undefined, 1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!searchEnabled) return;
    const timeout = window.setTimeout(() => {
      setPage(1);
      void refresh(query || undefined, 1);
    }, 300);
    return () => window.clearTimeout(timeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, searchEnabled]);

  const totalPages = Math.max(1, Math.ceil(total / pageLimit));

  const handlePageChange = (nextPage: number) => {
    if (nextPage < 1 || nextPage > totalPages) return;
    setPage(nextPage);
    void refresh(searchEnabled ? query || undefined : undefined, nextPage);
  };

  const runLeadAction = async (leadId: string, action: () => Promise<void>) => {
    setBusyLeadId(leadId);
    setActionError(null);
    try {
      await action();
      await refresh(searchEnabled ? query || undefined : undefined, page);
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Action failed. Please try again.');
    } finally {
      setBusyLeadId(null);
    }
  };

  const handleEmail = (lead: LeadDTO) => {
    if (!lead.email) {
      setActionError(`${lead.name} has no email address.`);
      return;
    }
    void runLeadAction(lead.id, async () => {
      const token = await getToken();
      await sendLeadEmail(token, lead.id);
    });
  };

  const handleWhatsApp = (lead: LeadDTO) => {
    if (!whatsappEnabled) {
      onUpgrade?.();
      return;
    }
    if (!lead.phone) {
      setActionError(`${lead.name} has no phone number.`);
      return;
    }
    void runLeadAction(lead.id, async () => {
      const token = await getToken();
      const res = await sendLeadWhatsApp(token, lead.id);
      window.open(res.url, '_blank', 'noopener,noreferrer');
    });
  };

  const handleDelete = (lead: LeadDTO) => {
    const confirmed = window.confirm(`Delete ${lead.name}? This cannot be undone.`);
    if (!confirmed) return;
    void runLeadAction(lead.id, async () => {
      const token = await getToken();
      await deleteLead(token, lead.id);
    });
  };

  const toggleSelected = (leadId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(leadId)) next.delete(leadId);
      else next.add(leadId);
      return next;
    });
  };

  const toggleSelectAllOnPage = () => {
    setSelectedIds((prev) =>
      prev.size === leads.length ? new Set() : new Set(leads.map((l) => l.id))
    );
  };

  const handleDeleteSelected = async () => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    const confirmed = window.confirm(
      `Delete ${ids.length} selected lead${ids.length === 1 ? '' : 's'}? This cannot be undone.`
    );
    if (!confirmed) return;
    setIsDeletingSelected(true);
    setActionError(null);
    try {
      const token = await getToken();
      await Promise.all(ids.map((id) => deleteLead(token, id)));
      setSelectedIds(new Set());
      await refresh(searchEnabled ? query || undefined : undefined, page);
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Failed to delete selected leads. Please try again.');
    } finally {
      setIsDeletingSelected(false);
    }
  };

  const handleEnrichSelected = async () => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    setIsEnriching(true);
    setActionError(null);
    setEnrichSummary(null);
    try {
      const token = await getToken();
      const res = await enrichLeads(token, ids);
      setEnrichSummary(
        `${res.dispatched} lead${res.dispatched === 1 ? '' : 's'} queued for enrichment — refresh in a moment to see updates.`
      );
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Failed to enrich selected leads. Please try again.');
    } finally {
      setIsEnriching(false);
    }
  };

  const handleDeleteAll = async () => {
    if (total === 0) return;
    const confirmed = window.confirm(
      `Delete all ${total.toLocaleString('en-US')} lead${total === 1 ? '' : 's'} in this workspace? This cannot be undone.`
    );
    if (!confirmed) return;
    setIsDeletingAll(true);
    setActionError(null);
    try {
      const token = await getToken();
      await deleteAllLeads(token);
      setPage(1);
      await refresh(undefined, 1);
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Failed to delete leads. Please try again.');
    } finally {
      setIsDeletingAll(false);
    }
  };

  const handleExport = async () => {
    setIsExporting(true);
    setActionError(null);
    try {
      const token = await getToken();
      const blob = await exportLeads(token, searchEnabled ? query || undefined : undefined);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = 'leads-export.csv';
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Export failed.');
    } finally {
      setIsExporting(false);
    }
  };

  if (!user) return null;

  const metaSuffix = tier === 'enterprise' ? ' · API access enabled' : '';

  return (
    <div className="mx-auto w-full max-w-[1180px]">
      <PageHeader
        title="Lead Center"
        description="Every captured lead, scored and ready to work. Actions run through your connected channels."
        action={
        <div className="flex flex-wrap gap-2">
            {bulkExportEnabled &&
            <Button variant="outline" onClick={() => void handleExport()} disabled={isExporting}>
                <DownloadIcon className="h-4 w-4" />
                {isExporting ? 'Exporting…' : 'Bulk export'}
              </Button>
            }
            <Button variant="outline" onClick={() => setDiscoverOpen(true)}>
              <CompassIcon className="h-4 w-4" />
              Find leads
            </Button>
            <Button
              variant="outline"
              onClick={() => (aiFilterEnabled ? setAiFilterOpen(true) : onUpgrade?.())}>

              <SparklesIcon className="h-4 w-4" />
              Filter your leads with AI
            </Button>
            <Button onClick={() => setAddOpen(true)}>
              <PlusIcon className="h-4 w-4" />
              Add lead
            </Button>
            {selectedIds.size > 0 &&
            <Button
              variant="outline"
              onClick={() => void handleEnrichSelected()}
              disabled={isEnriching}>

                <WandSparklesIcon className="h-4 w-4" />
                {isEnriching ? 'Enriching…' : `Enrich selected (${selectedIds.size})`}
              </Button>
            }
            {selectedIds.size > 0 &&
            <Button
              variant="outline"
              className="border-ember/40 text-ember hover:border-ember hover:bg-ember/10"
              onClick={() => void handleDeleteSelected()}
              disabled={isDeletingSelected}>

                <Trash2Icon className="h-4 w-4" />
                {isDeletingSelected ? 'Deleting…' : `Delete selected (${selectedIds.size})`}
              </Button>
            }
            {total > 0 &&
            <Button
              variant="outline"
              className="border-ember/40 text-ember hover:border-ember hover:bg-ember/10"
              onClick={() => void handleDeleteAll()}
              disabled={isDeletingAll}>

                <Trash2Icon className="h-4 w-4" />
                {isDeletingAll ? 'Deleting…' : 'Delete all'}
              </Button>
            }
          </div>
        } />


      {loadError &&
      <div
        role="alert"
        className="mb-4 flex flex-col gap-3 rounded-2xl border border-ember/40 bg-ember/10 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">

          <div className="flex items-start gap-3">
            <AlertCircleIcon className="mt-0.5 h-4 w-4 shrink-0 text-ember" aria-hidden="true" />
            <p className="text-[13.5px] text-ember">{loadError}</p>
          </div>
          <Button
          size="sm"
          variant="outline"
          onClick={() => void refresh(searchEnabled ? query || undefined : undefined, page)}>

            <RefreshCwIcon className="h-3.5 w-3.5" />
            Retry
          </Button>
        </div>
      }

      {actionError &&
      <div role="alert" className="mb-4 rounded-2xl border border-ember/40 bg-ember/10 px-5 py-3 text-[13.5px] text-ember">
          {actionError}
        </div>
      }

      {enrichSummary &&
      <div className="mb-4 rounded-2xl border border-signal/40 bg-signal/10 px-5 py-3 text-[13.5px] text-signal">
          {enrichSummary}
        </div>
      }

      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative w-full sm:max-w-[320px]">
          <SearchIcon
            className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-chalk-faint"
            aria-hidden="true" />

          <label htmlFor="lead-search" className="sr-only">
            Search leads
          </label>
          <input
            id="lead-search"
            value={searchEnabled ? query : ''}
            onChange={(e) => searchEnabled && setQuery(e.target.value)}
            disabled={!searchEnabled}
            title={searchEnabled ? undefined : 'Upgrade to Pro to search leads'}
            placeholder={searchEnabled ? 'Search name, email, phone, website…' : 'Search — upgrade to Pro'}
            className="h-11 w-full rounded-lg border border-ink-700 bg-ink-900 pl-10 pr-3.5 text-[14px] text-chalk placeholder:text-chalk-faint focus:border-signal focus:outline-none disabled:cursor-not-allowed disabled:opacity-55" />

        </div>
        <p className="font-mono text-[11.5px] uppercase tracking-wider text-chalk-faint">
          {leads.length} shown · {total.toLocaleString('en-US')} total{metaSuffix}
        </p>
      </div>

      <div className="overflow-x-auto rounded-2xl border border-ink-800 bg-ink-900 scrollbar-slim">
        <table className="w-full min-w-[1320px] border-collapse text-left">
          <caption className="sr-only">Leads in this workspace</caption>
          <thead>
            <tr className="border-b border-ink-800">
              <th scope="col" className="w-11 px-5 py-3.5">
                <input
                  type="checkbox"
                  aria-label="Select all leads on this page"
                  checked={leads.length > 0 && selectedIds.size === leads.length}
                  onChange={toggleSelectAllOnPage}
                  className="h-3.5 w-3.5 rounded border-ink-600 bg-ink-950 accent-signal" />

              </th>
              {['Name', 'Industry', 'Email', 'Phone', 'Website', 'Address', 'Completeness', 'Score', 'Status', 'Actions'].map((head) =>
              <th
                key={head}
                scope="col"
                className={cn(
                  'px-5 py-3.5 font-mono text-[10.5px] uppercase tracking-[0.16em] text-chalk-faint',
                  head === 'Actions' && 'text-right'
                )}>

                  {head}
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {isLoading &&
            <tr>
                <td colSpan={11} className="px-5 py-14 text-center text-[14px] text-chalk-dim">
                  Loading…
                </td>
              </tr>
            }
            {!isLoading && !loadError && leads.length === 0 &&
            <tr>
                <td colSpan={11} className="px-5 py-14 text-center text-[14px] text-chalk-dim">
                  {query && searchEnabled ?
                <>No leads match &ldquo;{query}&rdquo;.</> :
                'No leads yet — add your first one.'}
                </td>
              </tr>
            }
            {!isLoading && !loadError && leads.map((lead) =>
            <tr
              key={lead.id}
              onClick={() => setEditLead(lead)}
              className="cursor-pointer border-b border-ink-850 last:border-0 hover:bg-ink-850/60">

                <td className="px-5 py-4" onClick={(e) => e.stopPropagation()}>
                  <input
                    type="checkbox"
                    aria-label={`Select ${lead.name}`}
                    checked={selectedIds.has(lead.id)}
                    onChange={() => toggleSelected(lead.id)}
                    className="h-3.5 w-3.5 rounded border-ink-600 bg-ink-950 accent-signal" />

                </td>
                <td className="px-5 py-4">
                  <span className="block text-[14px] font-medium text-chalk">{lead.name}</span>
                </td>
                <td className="px-5 py-4 text-[13px] text-chalk-dim">{lead.industry ?? '—'}</td>
                <td className="px-5 py-4 text-[13.5px] text-chalk-dim">{lead.email ?? '—'}</td>
                <td className="px-5 py-4 font-mono text-[13px] text-chalk-dim">{lead.phone ?? '—'}</td>
                <td className="max-w-[160px] px-5 py-4 text-[13px] text-chalk-dim" onClick={(e) => e.stopPropagation()}>
                  {lead.website ?
                  <a
                    href={lead.website}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block truncate text-signal hover:underline">
                      {lead.website.replace(/^https?:\/\//, '')}
                    </a> :
                  '—'}
                </td>
                <td className="max-w-[180px] truncate px-5 py-4 text-[13px] text-chalk-dim">
                  {lead.address ?? '—'}
                </td>
                <td className="px-5 py-4">
                  {lead.completeness !== null ?
                  <span className="flex items-center gap-2">
                      <span className="h-1.5 w-12 overflow-hidden rounded-full bg-ink-800" aria-hidden="true">
                        <span
                      className={cn('block h-full rounded-full', lead.completeness >= 70 ? 'bg-signal' : 'bg-ink-600')}
                      style={{ width: `${lead.completeness}%` }} />

                      </span>
                      <span className="font-mono text-[13px] text-chalk">{lead.completeness}</span>
                    </span> :
                  <span className="font-mono text-[12px] text-chalk-faint">—</span>
                  }
                  {lead.enrichment_status === 'failed' &&
                  <span className="ml-2 font-mono text-[11px] text-ember" title="Enrichment failed">failed</span>
                  }
                </td>
                <td className="px-5 py-4">
                  {lead.scoring_failed ?
                <span className="font-mono text-[12px] text-ember" title="AI scoring failed">Score failed</span> :
                lead.score !== null ?
                <span className="flex items-center gap-2">
                      <span className="h-1.5 w-12 overflow-hidden rounded-full bg-ink-800" aria-hidden="true">
                        <span
                      className={cn('block h-full rounded-full', lead.score >= 70 ? 'bg-signal' : 'bg-ink-600')}
                      style={{ width: `${lead.score}%` }} />

                      </span>
                      <span className="font-mono text-[13px] text-chalk">{lead.score}</span>
                    </span> :

                <span className="font-mono text-[12px] text-chalk-faint">Scoring…</span>
                }
                </td>
                <td className="px-5 py-4">
                  <span
                  className={cn(
                    'inline-flex rounded-full border px-2.5 py-1 text-[11.5px] font-medium',
                    STATUS_STYLES[lead.status]
                  )}>

                    {lead.status}
                  </span>
                </td>
                <td className="px-5 py-4" onClick={(e) => e.stopPropagation()}>
                  <div className="flex items-center justify-end gap-1.5">
                    <IconAction
                    label={`Send email to ${lead.name}`}
                    icon={MailIcon}
                    disabled={busyLeadId === lead.id || !lead.email}
                    onClick={() => handleEmail(lead)} />

                    <IconAction
                    label={
                      whatsappEnabled ?
                      `Send WhatsApp to ${lead.name}` :
                      'Upgrade to Pro to access WhatsApp automation'
                    }
                    icon={MessageSquareIcon}
                    disabled={busyLeadId === lead.id || (whatsappEnabled && !lead.phone)}
                    onClick={() => handleWhatsApp(lead)} />

                    <IconAction
                    label={`Edit ${lead.name}`}
                    icon={PencilIcon}
                    disabled={busyLeadId === lead.id}
                    onClick={() => setEditLead(lead)} />

                    <IconAction
                    label={`Delete ${lead.name}`}
                    icon={Trash2Icon}
                    danger
                    disabled={busyLeadId === lead.id}
                    onClick={() => handleDelete(lead)} />

                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {totalPages > 1 &&
      <div className="mt-4 flex items-center justify-between gap-3">
          <p className="font-mono text-[11.5px] text-chalk-faint">
            Page {page} of {totalPages}
          </p>
          <div className="flex gap-2">
            <Button size="sm" variant="outline" disabled={page <= 1 || isLoading} onClick={() => handlePageChange(page - 1)}>
              <ChevronLeftIcon className="h-4 w-4" />
              Previous
            </Button>
            <Button
            size="sm"
            variant="outline"
            disabled={page >= totalPages || isLoading}
            onClick={() => handlePageChange(page + 1)}>

              Next
              <ChevronRightIcon className="h-4 w-4" />
            </Button>
          </div>
        </div>
      }

      {tier === 'free' &&
      <div className="mt-4 flex flex-col gap-3 rounded-2xl border border-ink-800 bg-ink-900 p-5 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-[13.5px] text-chalk-dim">
            Free workspaces show {pageLimit} leads per page and cap at {user.workspace.leadQuota} per
            month. Search, bulk actions and WhatsApp unlock on Pro.
          </p>
          <Button size="sm" onClick={onUpgrade}>
            Upgrade to Pro
          </Button>
        </div>
      }

      <AddLeadModal
        open={addOpen}
        onClose={() => setAddOpen(false)}
        onCreated={() => void refresh(searchEnabled ? query || undefined : undefined, page)} />

      <EditLeadModal
        lead={editLead}
        onClose={() => setEditLead(null)}
        onUpdated={() => void refresh(searchEnabled ? query || undefined : undefined, page)} />

      <LeadDiscoveryModal
        open={discoverOpen}
        onClose={() => setDiscoverOpen(false)}
        onImported={() => void refresh(searchEnabled ? query || undefined : undefined, page)}
        onWantManualAdd={() => {
          setDiscoverOpen(false);
          setAddOpen(true);
        }}
        resultCap={discoveryCap}
        enhancedTier={discoveryEnhanced} />

      {aiFilterEnabled &&
      <AiLeadFilterModal open={aiFilterOpen} onClose={() => setAiFilterOpen(false)} />
      }

    </div>);

}

interface IconActionProps {
  label: string;
  icon: React.ComponentType<{className?: string;}>;
  disabled?: boolean;
  danger?: boolean;
  onClick?: () => void;
}

function IconAction({ label, icon: Icon, disabled = false, danger = false, onClick }: IconActionProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      title={label}
      aria-disabled={disabled}
      className={cn(
        'inline-flex h-8 w-8 items-center justify-center rounded-lg border border-ink-700 transition-colors',
        disabled ?
        'cursor-not-allowed text-ink-500' :
        danger ?
        'text-chalk-dim hover:border-ember/50 hover:text-ember' :
        'text-chalk-dim hover:border-signal/50 hover:text-signal'
      )}>

      <Icon className="h-3.5 w-3.5" />
    </button>);

}
