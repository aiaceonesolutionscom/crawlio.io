import React, { useMemo, useState } from 'react';
import { MailIcon, MessageSquareIcon, PencilIcon, PlusIcon, SearchIcon, Trash2Icon } from 'lucide-react';
import { PageHeader } from '../../../shared/layout/PageHeader';
import { Button } from '../../../shared/ui/Button';
import { useSession } from '../../../contexts/SessionContext';
import { LEADS } from '../../../data/leads';
import { cn } from '../../../shared/utils/cn';
import type { LeadStatus } from '../../../types';

const STATUS_STYLES: Record<LeadStatus, string> = {
  New: 'border-ink-600 text-chalk-dim',
  Qualified: 'border-signal/50 text-signal',
  Contacted: 'border-sky-soft/50 text-sky-soft',
  Nurturing: 'border-ember/40 text-ember',
  Won: 'border-signal text-signal',
  Lost: 'border-ink-700 text-chalk-faint'
};

export function Leads() {
  const { user } = useSession();
  const [query, setQuery] = useState('');
  if (!user) return null;

  const rows = useMemo(() => {
    if (!query.trim()) return LEADS;
    return LEADS.filter((lead) =>
    [lead.name, lead.company, lead.email].join(' ').toLowerCase().includes(query.trim().toLowerCase())
    );
  }, [query]);

  return (
    <div className="mx-auto w-full max-w-[1180px]">
      <PageHeader
        title="Lead Center"
        description="Every captured lead, scored and ready to work. Actions run through your connected channels."
        action={
        <Button>
            <PlusIcon className="h-4 w-4" />
            Add lead
          </Button>
        } />


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
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search name, company or email"
            className="h-11 w-full rounded-lg border border-ink-700 bg-ink-900 pl-10 pr-3.5 text-[14px] text-chalk placeholder:text-chalk-faint focus:border-signal focus:outline-none" />

        </div>
        <p className="font-mono text-[11.5px] uppercase tracking-wider text-chalk-faint">
          {rows.length} shown · {user.workspace.leadsUsed.toLocaleString('en-US')} total
        </p>
      </div>

      <div className="overflow-x-auto rounded-2xl border border-ink-800 bg-ink-900 scrollbar-slim">
        <table className="w-full min-w-[900px] border-collapse text-left">
          <caption className="sr-only">Leads in this workspace</caption>
          <thead>
            <tr className="border-b border-ink-800">
              {['Name', 'Email', 'Phone', 'Score', 'Status', 'Actions'].map((head) =>
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
            {rows.length === 0 &&
            <tr>
                <td colSpan={6} className="px-5 py-14 text-center text-[14px] text-chalk-dim">
                  No leads match &ldquo;{query}&rdquo;.
                </td>
              </tr>
            }
            {rows.map((lead) =>
            <tr key={lead.id} className="border-b border-ink-850 last:border-0 hover:bg-ink-850/60">
                <td className="px-5 py-4">
                  <span className="block text-[14px] font-medium text-chalk">{lead.name}</span>
                  <span className="block text-[12.5px] text-chalk-faint">{lead.company}</span>
                </td>
                <td className="px-5 py-4 text-[13.5px] text-chalk-dim">{lead.email}</td>
                <td className="px-5 py-4 font-mono text-[13px] text-chalk-dim">{lead.phone}</td>
                <td className="px-5 py-4">
                  <span className="flex items-center gap-2">
                    <span className="h-1.5 w-12 overflow-hidden rounded-full bg-ink-800" aria-hidden="true">
                      <span
                      className={cn('block h-full rounded-full', lead.score >= 70 ? 'bg-signal' : 'bg-ink-600')}
                      style={{ width: `${lead.score}%` }} />

                    </span>
                    <span className="font-mono text-[13px] text-chalk">{lead.score}</span>
                  </span>
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
                <td className="px-5 py-4">
                  <div className="flex items-center justify-end gap-1.5">
                    <IconAction label={`Send email to ${lead.name}`} icon={MailIcon} />
                    <IconAction label={`Send WhatsApp to ${lead.name}`} icon={MessageSquareIcon} />
                    <IconAction label={`Edit ${lead.name}`} icon={PencilIcon} />
                    <IconAction label={`Delete ${lead.name}`} icon={Trash2Icon} danger />
                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
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
