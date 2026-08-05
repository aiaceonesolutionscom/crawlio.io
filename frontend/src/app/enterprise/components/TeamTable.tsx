import React, { useCallback, useEffect, useState } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { Trash2Icon } from 'lucide-react';
import { listTeam, removeTeamEntry, type TeamEntryDTO } from '../../../lib/api/team';
import { useSession } from '../../../contexts/SessionContext';
import { formatQuota } from '../../../utils/plan';
import { cn } from '../../../shared/utils/cn';

interface Props {
  refreshKey: number;
}

export function TeamTable({ refreshKey }: Props) {
  const { getToken } = useAuth();
  const { refreshWorkspace } = useSession();
  const [items, setItems] = useState<TeamEntryDTO[]>([]);
  const [seatsUsed, setSeatsUsed] = useState(0);
  const [seatQuota, setSeatQuota] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    const token = await getToken();
    const res = await listTeam(token);
    setItems(res.items);
    setSeatsUsed(res.seats_used);
    setSeatQuota(res.seat_quota);
    setIsLoading(false);
  }, [getToken]);

  useEffect(() => {
    void refresh();
  }, [refresh, refreshKey]);

  const handleRemove = async (entry: TeamEntryDTO) => {
    setBusyId(entry.id);
    const token = await getToken();
    await removeTeamEntry(token, entry.id);
    await refresh();
    void refreshWorkspace();
    setBusyId(null);
  };

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-ink-800 bg-ink-900 p-5">
        <p className="text-[14px] font-medium text-chalk">
          {seatsUsed} of {formatQuota(seatQuota)} seats used
        </p>
        <p className="mt-1 text-[13px] text-chalk-faint">
          Unlimited seats with custom roles — provision as many teammates as you need.
        </p>
      </div>

      <div className="overflow-x-auto rounded-2xl border border-ink-800 bg-ink-900 scrollbar-slim">
        <table className="w-full min-w-[620px] border-collapse text-left">
          <caption className="sr-only">Workspace members</caption>
          <thead>
            <tr className="border-b border-ink-800">
              {['Member', 'Email', 'Role', 'Status', 'Actions'].map((head) =>
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
                <td colSpan={5} className="px-5 py-14 text-center text-[14px] text-chalk-dim">
                  Loading…
                </td>
              </tr>
            }
            {!isLoading && items.map((member) =>
            <tr key={member.id} className="border-b border-ink-850 last:border-0">
                <td className="px-5 py-4 text-[14px] font-medium text-chalk">{member.name ?? '—'}</td>
                <td className="px-5 py-4 text-[13.5px] text-chalk-dim">{member.email ?? '—'}</td>
                <td className="px-5 py-4 text-[13.5px] text-chalk-dim">{member.role}</td>
                <td className="px-5 py-4">
                  <span
                  className={cn(
                    'inline-flex rounded-full border px-2.5 py-1 text-[11.5px] font-medium',
                    member.status === 'Active' ?
                    'border-signal/50 text-signal' :
                    'border-ink-600 text-chalk-faint'
                  )}>

                    {member.status}
                  </span>
                </td>
                <td className="px-5 py-4 text-right">
                  {member.role !== 'Owner' &&
                <button
                  type="button"
                  onClick={() => handleRemove(member)}
                  disabled={busyId === member.id}
                  aria-label={`Remove ${member.email ?? member.name ?? 'member'}`}
                  className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-ink-700 text-chalk-dim hover:border-ember/50 hover:text-ember disabled:opacity-50">

                      <Trash2Icon className="h-3.5 w-3.5" />
                    </button>
                }
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>);

}
