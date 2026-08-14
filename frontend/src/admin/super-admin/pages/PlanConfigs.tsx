import React, { useCallback, useState } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { EditIcon } from 'lucide-react';
import { PageHeader } from '../../../shared/layout/PageHeader';
import { AdminResourceTable, type AdminColumn } from '../../components/AdminResourceTable';
import { AdminResourceForm, type AdminField } from '../../components/AdminResourceForm';
import { useAdminResource } from '../../lib/useAdminResource';
import { listPlanConfigs, updatePlanConfig, type PlanConfigDTO } from '../../../lib/api/admin/planConfigs';

const FIELDS: AdminField[] = [
  { key: 'display_name', label: 'Display name', type: 'text' },
  { key: 'lead_quota', label: 'Lead quota', type: 'number' },
  { key: 'seat_quota', label: 'Seat quota', type: 'number' },
  { key: 'discovery_result_limit', label: 'Discovery results per search', type: 'number' },
  { key: 'daily_discovery_import_limit', label: 'Daily discovery import limit', type: 'number' },
  { key: 'daily_email_limit', label: 'Daily email send limit', type: 'number' },
  {
    key: 'capabilities',
    label: 'Capabilities (JSON list)',
    type: 'json',
    helpText: 'e.g. ["leads", "team", "automation", "email_agent"] — gates plan-locked features server-side.'
  },
  { key: 'is_active', label: 'Active', type: 'boolean' }
];

export function PlanConfigs() {
  const { getToken } = useAuth();
  const fetchList = useCallback(() => getToken().then((t) => listPlanConfigs(t)), [getToken]);
  const { items, isLoading, refresh } = useAdminResource(fetchList);
  const [editing, setEditing] = useState<PlanConfigDTO | null>(null);

  const columns: AdminColumn<PlanConfigDTO>[] = [
    { key: 'plan_key', header: 'Plan' },
    { key: 'lead_quota', header: 'Leads' },
    { key: 'seat_quota', header: 'Seats' },
    { key: 'daily_email_limit', header: 'Daily emails' },
    { key: 'capabilities', header: 'Capabilities', render: (row) => <span className="text-[12px]">{row.capabilities.join(', ')}</span> }
  ];

  return (
    <div>
      <PageHeader
        title="Plans & limits"
        description="What every plan can do and how much it gets. Edits here take effect immediately for every workspace on that plan — no deploy needed."
      />

      {editing && (
        <div className="mb-6 rounded-2xl border border-ink-800 bg-ink-900 p-5">
          <p className="mb-4 text-[14px] font-medium text-chalk">Edit {editing.display_name}</p>
          <AdminResourceForm
            fields={FIELDS}
            initialValues={editing as unknown as Record<string, unknown>}
            onCancel={() => setEditing(null)}
            onSubmit={async (values) => {
              const token = await getToken();
              await updatePlanConfig(token, editing.plan_key, values);
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
        getRowId={(row) => row.plan_key}
        renderActions={(row) => (
          <button
            type="button"
            onClick={() => setEditing(row)}
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-ink-700 text-chalk-dim hover:border-signal/50 hover:text-signal"
            aria-label={`Edit ${row.display_name}`}
          >
            <EditIcon className="h-3.5 w-3.5" />
          </button>
        )}
      />
    </div>
  );
}
