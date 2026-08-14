import React, { useCallback, useState } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { EditIcon, Trash2Icon } from 'lucide-react';
import { PageHeader } from '../../../shared/layout/PageHeader';
import { AdminResourceTable, type AdminColumn } from '../../components/AdminResourceTable';
import { AdminResourceForm, type AdminField } from '../../components/AdminResourceForm';
import { useAdminResource } from '../../lib/useAdminResource';
import { useAdminSession } from '../../../contexts/AdminSessionContext';
import {
  deleteWorkspace,
  listWorkspaces,
  updateWorkspace,
  type AdminWorkspaceDTO
} from '../../../lib/api/admin/workspaces';

const FIELDS: AdminField[] = [
  { key: 'name', label: 'Name', type: 'text' },
  {
    key: 'plan',
    label: 'Plan',
    type: 'select',
    options: [
      { label: 'Free', value: 'free' },
      { label: 'Pro', value: 'pro' },
      { label: 'Enterprise', value: 'enterprise' }
    ]
  },
  { key: 'lead_quota', label: 'Lead quota', type: 'number', helpText: 'Overrides the plan default for this workspace only.' },
  { key: 'seat_quota', label: 'Seat quota', type: 'number' }
];

export function Workspaces() {
  const { getToken } = useAuth();
  const { admin } = useAdminSession();
  const canWrite = admin?.permissions.includes('workspaces.write') ?? false;
  const [search, setSearch] = useState('');
  const fetchList = useCallback(() => getToken().then((t) => listWorkspaces(t, search || undefined)), [getToken, search]);
  const { items, isLoading, refresh } = useAdminResource(fetchList);
  const [editing, setEditing] = useState<AdminWorkspaceDTO | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const columns: AdminColumn<AdminWorkspaceDTO>[] = [
    { key: 'name', header: 'Name' },
    { key: 'plan', header: 'Plan' },
    {
      key: 'usage',
      header: 'Usage',
      render: (row) => (
        <div className="space-y-1 font-mono text-[11.5px] text-chalk-dim">
          <p>
            Leads <span className="text-chalk">{row.lead_count}</span>
            <span className="text-chalk-faint"> / {row.lead_quota.toLocaleString()}</span>
          </p>
          <p>
            Seats <span className="text-chalk">{row.member_count}</span>
            <span className="text-chalk-faint"> / {row.seat_quota}</span>
          </p>
          <p>
            Emails <span className="text-chalk">{row.email_count}</span>
          </p>
        </div>
      )
    },
    { key: 'id', header: 'Workspace ID', render: (row) => <span className="font-mono text-[11px]">{row.id}</span> }
  ];

  const handleDelete = async (workspace: AdminWorkspaceDTO) => {
    if (!confirm(`Delete workspace "${workspace.name}" and ALL its data? This cannot be undone.`)) return;
    setBusyId(workspace.id);
    const token = await getToken();
    await deleteWorkspace(token, workspace.id);
    await refresh();
    setBusyId(null);
  };

  return (
    <div>
      <PageHeader
        title="Workspaces"
        description="Every tenant on the platform. Edit plan/quotas or drill in to fix customer data."
        action={
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name…"
            className="h-10 rounded-lg border border-ink-700 bg-ink-950 px-3 text-[13.5px] text-chalk outline-none focus:border-signal/60"
          />
        }
      />

      {editing && canWrite && (
        <div className="mb-6 rounded-2xl border border-ink-800 bg-ink-900 p-5">
          <p className="mb-4 text-[14px] font-medium text-chalk">Edit {editing.name}</p>
          <AdminResourceForm
            fields={FIELDS}
            initialValues={editing as unknown as Record<string, unknown>}
            onCancel={() => setEditing(null)}
            onSubmit={async (values) => {
              const token = await getToken();
              await updateWorkspace(token, editing.id, values);
              setEditing(null);
              await refresh();
            }}
          />
        </div>
      )}

      <AdminResourceTable
        columns={columns}
        rows={items}
        isLoading={isLoading}
        getRowId={(row) => row.id}
        renderActions={
          canWrite
            ? (row) => (
                <div className="flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => setEditing(row)}
                    className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-ink-700 text-chalk-dim hover:border-signal/50 hover:text-signal"
                    aria-label={`Edit ${row.name}`}
                  >
                    <EditIcon className="h-3.5 w-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDelete(row)}
                    disabled={busyId === row.id}
                    className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-ink-700 text-chalk-dim hover:border-ember/50 hover:text-ember disabled:opacity-50"
                    aria-label={`Delete ${row.name}`}
                  >
                    <Trash2Icon className="h-3.5 w-3.5" />
                  </button>
                </div>
              )
            : undefined
        }
      />
    </div>
  );
}
