import React, { useCallback, useState } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { EditIcon, Trash2Icon } from 'lucide-react';
import { PageHeader } from '../../shared/layout/PageHeader';
import { Button } from '../../shared/ui/Button';
import { AdminResourceTable, type AdminColumn } from '../components/AdminResourceTable';
import { AdminResourceForm, type AdminField } from '../components/AdminResourceForm';
import { useAdminResource } from '../lib/useAdminResource';
import {
  deleteSystemSetting,
  listSystemSettings,
  upsertSystemSetting,
  type SystemSettingDTO
} from '../../lib/api/admin/systemSettings';

const VALUE_TYPE_OPTIONS = [
  { label: 'string', value: 'string' },
  { label: 'number', value: 'number' },
  { label: 'boolean', value: 'boolean' },
  { label: 'json', value: 'json' }
];

const CREATE_FIELDS: AdminField[] = [
  { key: 'key', label: 'Key', type: 'text', helpText: 'e.g. maintenance_mode — unique, used by code to look this up.' },
  {
    key: 'value',
    label: 'Value (JSON)',
    type: 'json',
    helpText: 'Quote strings ("hello"), plain numbers (42), true/false, or an object/array.'
  },
  { key: 'value_type', label: 'Value type', type: 'select', options: VALUE_TYPE_OPTIONS },
  { key: 'description', label: 'Description', type: 'textarea' }
];

const EDIT_FIELDS: AdminField[] = [
  {
    key: 'value',
    label: 'Value (JSON)',
    type: 'json',
    helpText: 'Quote strings ("hello"), plain numbers (42), true/false, or an object/array.'
  },
  { key: 'value_type', label: 'Value type', type: 'select', options: VALUE_TYPE_OPTIONS },
  { key: 'description', label: 'Description', type: 'textarea' }
];

export function SystemSettings() {
  const { getToken } = useAuth();
  const fetchList = useCallback(() => getToken().then((t) => listSystemSettings(t)), [getToken]);
  const { items, isLoading, refresh } = useAdminResource(fetchList);

  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<SystemSettingDTO | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleDelete = async (setting: SystemSettingDTO) => {
    if (!confirm(`Delete setting "${setting.key}"?`)) return;
    setError(null);
    try {
      const token = await getToken();
      await deleteSystemSetting(token, setting.key);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete setting');
    }
  };

  const columns: AdminColumn<SystemSettingDTO>[] = [
    { key: 'key', header: 'Key' },
    { key: 'value', header: 'Value', render: (row) => <span className="font-mono text-[12px]">{JSON.stringify(row.value)}</span> },
    { key: 'value_type', header: 'Type' },
    { key: 'description', header: 'Description', render: (row) => row.description ?? '—' },
    { key: 'updated_by', header: 'Updated by', render: (row) => row.updated_by ?? '—' }
  ];

  return (
    <div>
      <PageHeader
        title="System settings"
        description="Generic platform key/value config, editable live — no code change or redeploy needed."
      />

      {error && <p className="mb-4 text-[13px] text-ember">{error}</p>}

      {!creating && !editing && (
        <div className="mb-6">
          <Button size="sm" onClick={() => setCreating(true)}>
            New setting
          </Button>
        </div>
      )}

      {creating && (
        <div className="mb-6 rounded-2xl border border-ink-800 bg-ink-900 p-5">
          <p className="mb-4 text-[14px] font-medium text-chalk">New system setting</p>
          <AdminResourceForm
            fields={CREATE_FIELDS}
            initialValues={{ value_type: 'string' }}
            onCancel={() => setCreating(false)}
            onSubmit={async (values) => {
              const { key, ...rest } = values as { key: string; value: unknown; value_type: string; description?: string };
              const token = await getToken();
              await upsertSystemSetting(token, key, rest);
              setCreating(false);
              await refresh();
            }}
          />
        </div>
      )}

      {editing && (
        <div className="mb-6 rounded-2xl border border-ink-800 bg-ink-900 p-5">
          <p className="mb-4 text-[14px] font-medium text-chalk">Edit {editing.key}</p>
          <AdminResourceForm
            fields={EDIT_FIELDS}
            initialValues={editing as unknown as Record<string, unknown>}
            onCancel={() => setEditing(null)}
            onSubmit={async (values) => {
              const token = await getToken();
              await upsertSystemSetting(
                token,
                editing.key,
                values as { value: unknown; value_type: string; description?: string }
              );
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
        getRowId={(row) => row.key}
        renderActions={(row) => (
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setEditing(row)}
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-ink-700 text-chalk-dim hover:border-signal/50 hover:text-signal"
              aria-label={`Edit ${row.key}`}
            >
              <EditIcon className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              onClick={() => handleDelete(row)}
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-ink-700 text-chalk-dim hover:border-ember/50 hover:text-ember"
              aria-label={`Delete ${row.key}`}
            >
              <Trash2Icon className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      />
    </div>
  );
}
