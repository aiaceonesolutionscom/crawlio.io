import React from 'react';
import { TEAM } from '../../../data/metrics';
import { formatQuota } from '../../../utils/plan';
import { cn } from '../../../shared/utils/cn';
import type { Workspace } from '../../../types';

interface Props {
  workspace: Workspace;
}

export function TeamTable({ workspace }: Props) {
  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-ink-800 bg-ink-900 p-5">
        <p className="text-[14px] font-medium text-chalk">
          {workspace.seatsUsed} of {formatQuota(workspace.seatQuota)} seats used
        </p>
        <p className="mt-1 text-[13px] text-chalk-faint">
          Seat limits are enforced server-side — invites beyond your plan are blocked.
        </p>
      </div>

      <div className="overflow-x-auto rounded-2xl border border-ink-800 bg-ink-900 scrollbar-slim">
        <table className="w-full min-w-[620px] border-collapse text-left">
          <caption className="sr-only">Workspace members</caption>
          <thead>
            <tr className="border-b border-ink-800">
              {['Member', 'Email', 'Role', 'Status'].map((head) =>
              <th
                key={head}
                scope="col"
                className="px-5 py-3.5 font-mono text-[10.5px] uppercase tracking-[0.16em] text-chalk-faint">

                  {head}
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {TEAM.map((member) =>
            <tr key={member.id} className="border-b border-ink-850 last:border-0">
                <td className="px-5 py-4 text-[14px] font-medium text-chalk">{member.name}</td>
                <td className="px-5 py-4 text-[13.5px] text-chalk-dim">{member.email}</td>
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
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>);

}
