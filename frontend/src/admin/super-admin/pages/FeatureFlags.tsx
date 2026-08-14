import React, { useCallback, useEffect, useState } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { EditIcon, SlidersHorizontalIcon, Trash2Icon } from 'lucide-react';
import { PageHeader } from '../../../shared/layout/PageHeader';
import { Button } from '../../../shared/ui/Button';
import { AdminResourceTable, type AdminColumn } from '../../components/AdminResourceTable';
import { AdminResourceForm, type AdminField } from '../../components/AdminResourceForm';
import { useAdminResource } from '../../lib/useAdminResource';
import {
  clearOverride,
  createFeatureFlag,
  deleteFeatureFlag,
  listFeatureFlags,
  listOverrides,
  setOverride,
  updateFeatureFlag,
  type FeatureFlagDTO,
  type FeatureFlagOverrideDTO
} from '../../../lib/api/admin/featureFlags';

const CREATE_FIELDS: AdminField[] = [
  { key: 'key', label: 'Key', type: 'text', helpText: 'e.g. beta_ui — unique, used by code to check this flag.' },
  { key: 'description', label: 'Description', type: 'textarea' },
  { key: 'default_enabled', label: 'Default enabled', type: 'boolean' }
];

const EDIT_FIELDS: AdminField[] = [
  { key: 'description', label: 'Description', type: 'textarea' },
  { key: 'default_enabled', label: 'Default enabled', type: 'boolean' }
];

export function FeatureFlags() {
  const { getToken } = useAuth();
  const fetchList = useCallback(() => getToken().then((t) => listFeatureFlags(t)), [getToken]);
  const { items, isLoading, refresh } = useAdminResource(fetchList);

  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<FeatureFlagDTO | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [selectedFlag, setSelectedFlag] = useState<FeatureFlagDTO | null>(null);
  const [overrides, setOverrides] = useState<FeatureFlagOverrideDTO[]>([]);
  const [overridesLoading, setOverridesLoading] = useState(false);
  const [newOverrideWorkspaceId, setNewOverrideWorkspaceId] = useState('');
  const [newOverrideEnabled, setNewOverrideEnabled] = useState(true);

  const loadOverrides = useCallback(async () => {
    if (!selectedFlag) return;
    setOverridesLoading(true);
    try {
      const token = await getToken();
      setOverrides(await listOverrides(token, selectedFlag.id));
    } finally {
      setOverridesLoading(false);
    }
  }, [selectedFlag, getToken]);

  useEffect(() => {
    void loadOverrides();
  }, [loadOverrides]);

  const handleDelete = async (flag: FeatureFlagDTO) => {
    if (!confirm(`Delete flag "${flag.key}"? This also removes all its workspace overrides.`)) return;
    setError(null);
    try {
      const token = await getToken();
      await deleteFeatureFlag(token, flag.id);
      if (selectedFlag?.id === flag.id) setSelectedFlag(null);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete flag');
    }
  };

  const handleAddOverride = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFlag || !newOverrideWorkspaceId.trim()) return;
    setError(null);
    try {
      const token = await getToken();
      await setOverride(token, selectedFlag.id, newOverrideWorkspaceId.trim(), newOverrideEnabled);
      setNewOverrideWorkspaceId('');
      await loadOverrides();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to set override');
    }
  };

  const handleClearOverride = async (workspaceId: string) => {
    if (!selectedFlag) return;
    setError(null);
    try {
      const token = await getToken();
      await clearOverride(token, selectedFlag.id, workspaceId);
      await loadOverrides();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to clear override');
    }
  };

  const columns: AdminColumn<FeatureFlagDTO>[] = [
    { key: 'key', header: 'Key' },
    { key: 'description', header: 'Description', render: (row) => row.description ?? '—' },
    {
      key: 'default_enabled',
      header: 'Default',
      render: (row) => (row.default_enabled ? 'On' : 'Off')
    }
  ];

  return (
    <div>
      <PageHeader
        title="Feature flags"
        description="Toggle behavior platform-wide or per workspace, without a deploy. Overrides always win over the default."
      />

      {error && <p className="mb-4 text-[13px] text-ember">{error}</p>}

      {!creating && !editing && (
        <div className="mb-6">
          <Button size="sm" onClick={() => setCreating(true)}>
            New flag
          </Button>
        </div>
      )}

      {creating && (
        <div className="mb-6 rounded-2xl border border-ink-800 bg-ink-900 p-5">
          <p className="mb-4 text-[14px] font-medium text-chalk">New feature flag</p>
          <AdminResourceForm
            fields={CREATE_FIELDS}
            initialValues={{ default_enabled: false }}
            onCancel={() => setCreating(false)}
            onSubmit={async (values) => {
              const token = await getToken();
              await createFeatureFlag(token, values as { key: string; description?: string; default_enabled?: boolean });
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
              await updateFeatureFlag(token, editing.id, values as { description?: string; default_enabled?: boolean });
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
        renderActions={(row) => (
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setSelectedFlag(row)}
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-ink-700 text-chalk-dim hover:border-signal/50 hover:text-signal"
              aria-label={`Manage overrides for ${row.key}`}
            >
              <SlidersHorizontalIcon className="h-3.5 w-3.5" />
            </button>
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

      {selectedFlag && (
        <div className="mt-8 rounded-2xl border border-ink-800 bg-ink-900 p-5">
          <div className="mb-4 flex items-center justify-between">
            <p className="text-[14px] font-medium text-chalk">
              Overrides for <span className="text-signal">{selectedFlag.key}</span>
            </p>
            <button type="button" onClick={() => setSelectedFlag(null)} className="text-[12.5px] text-chalk-faint hover:text-chalk">
              Close
            </button>
          </div>

          <form onSubmit={handleAddOverride} className="mb-4 flex flex-wrap items-end gap-3">
            <div className="space-y-1.5">
              <label htmlFor="override-workspace-id" className="block text-[12.5px] font-medium text-chalk-dim">
                Workspace ID
              </label>
              <input
                id="override-workspace-id"
                value={newOverrideWorkspaceId}
                onChange={(e) => setNewOverrideWorkspaceId(e.target.value)}
                placeholder="workspace id"
                className="h-10 w-72 rounded-lg border border-ink-700 bg-ink-950 px-3 text-[13.5px] text-chalk outline-none focus:border-signal/60"
              />
            </div>
            <label className="flex items-center gap-2 pb-2.5 text-[13.5px] text-chalk">
              <input
                type="checkbox"
                checked={newOverrideEnabled}
                onChange={(e) => setNewOverrideEnabled(e.target.checked)}
              />
              Enabled
            </label>
            <Button type="submit" size="sm">
              Set override
            </Button>
          </form>

          <AdminResourceTable
            columns={[
              { key: 'workspace_id', header: 'Workspace' },
              { key: 'is_enabled', header: 'Enabled', render: (row) => (row.is_enabled ? 'Yes' : 'No') }
            ]}
            rows={overrides}
            isLoading={overridesLoading}
            getRowId={(row) => row.id}
            emptyMessage="No overrides — this flag uses its default for every workspace."
            renderActions={(row) => (
              <button
                type="button"
                onClick={() => handleClearOverride(row.workspace_id)}
                className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-ink-700 text-chalk-dim hover:border-ember/50 hover:text-ember"
                aria-label={`Clear override for ${row.workspace_id}`}
              >
                <Trash2Icon className="h-3.5 w-3.5" />
              </button>
            )}
          />
        </div>
      )}
    </div>
  );
}
