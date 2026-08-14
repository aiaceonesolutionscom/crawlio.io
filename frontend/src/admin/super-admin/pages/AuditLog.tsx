import React, { useCallback, useState } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { PageHeader } from '../../../shared/layout/PageHeader';
import { AdminResourceTable, type AdminColumn } from '../../components/AdminResourceTable';
import { useAdminResource } from '../../lib/useAdminResource';
import { listAuditLog, type AuditLogDTO } from '../../../lib/api/admin/auditLog';

function DiffCell({ before, after }: { before: Record<string, unknown> | null; after: Record<string, unknown> | null }) {
  if (!before && !after) return <span className="text-chalk-faint">—</span>;
  return (
    <details className="text-[12px]">
      <summary className="cursor-pointer text-chalk-faint hover:text-chalk">View</summary>
      <div className="mt-2 space-y-2">
        {before && (
          <div>
            <p className="font-mono text-[10px] uppercase tracking-wider text-chalk-faint">Before</p>
            <pre className="mt-1 max-w-[320px] overflow-x-auto rounded bg-ink-950 p-2 text-[11px] text-chalk-dim">
              {JSON.stringify(before, null, 2)}
            </pre>
          </div>
        )}
        {after && (
          <div>
            <p className="font-mono text-[10px] uppercase tracking-wider text-chalk-faint">After</p>
            <pre className="mt-1 max-w-[320px] overflow-x-auto rounded bg-ink-950 p-2 text-[11px] text-chalk-dim">
              {JSON.stringify(after, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </details>
  );
}

export function AuditLog() {
  const { getToken } = useAuth();
  const [actionFilter, setActionFilter] = useState('');
  const [targetTypeFilter, setTargetTypeFilter] = useState('');

  const fetchList = useCallback(
    () =>
      getToken().then((t) =>
        listAuditLog(t, {
          action: actionFilter || undefined,
          targetType: targetTypeFilter || undefined
        })
      ),
    [getToken, actionFilter, targetTypeFilter]
  );
  const { items, isLoading, refresh } = useAdminResource(fetchList);

  const columns: AdminColumn<AuditLogDTO>[] = [
    { key: 'created_at', header: 'When', render: (row) => new Date(row.created_at).toLocaleString() },
    { key: 'actor_email', header: 'Actor' },
    { key: 'action', header: 'Action' },
    {
      key: 'target',
      header: 'Target',
      render: (row) => (
        <span>
          {row.target_type}
          {row.target_id ? `:${row.target_id}` : ''}
        </span>
      )
    },
    { key: 'workspace_id', header: 'Workspace' },
    { key: 'diff', header: 'Diff', render: (row) => <DiffCell before={row.before} after={row.after} /> }
  ];

  return (
    <div>
      <PageHeader
        title="Audit log"
        description="Every admin mutation across the platform — who did what, when, and the before/after values."
      />

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void refresh();
        }}
        className="mb-6 flex flex-wrap items-end gap-3 rounded-2xl border border-ink-800 bg-ink-900 p-5"
      >
        <div className="space-y-1.5">
          <label htmlFor="action-filter" className="block text-[12.5px] font-medium text-chalk-dim">
            Action
          </label>
          <input
            id="action-filter"
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            placeholder="e.g. workspace.update"
            className="h-10 w-56 rounded-lg border border-ink-700 bg-ink-950 px-3 text-[13.5px] text-chalk outline-none focus:border-signal/60"
          />
        </div>
        <div className="space-y-1.5">
          <label htmlFor="target-type-filter" className="block text-[12.5px] font-medium text-chalk-dim">
            Target type
          </label>
          <input
            id="target-type-filter"
            value={targetTypeFilter}
            onChange={(e) => setTargetTypeFilter(e.target.value)}
            placeholder="e.g. workspace"
            className="h-10 w-56 rounded-lg border border-ink-700 bg-ink-950 px-3 text-[13.5px] text-chalk outline-none focus:border-signal/60"
          />
        </div>
        <button
          type="submit"
          className="h-10 rounded-lg border border-ink-700 px-4 text-[13.5px] text-chalk-dim hover:text-chalk"
        >
          Filter
        </button>
      </form>

      <AdminResourceTable columns={columns} rows={items} isLoading={isLoading} getRowId={(row) => row.id} />
    </div>
  );
}
