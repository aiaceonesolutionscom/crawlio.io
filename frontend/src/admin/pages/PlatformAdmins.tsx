import React, { useCallback, useState } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { Trash2Icon } from 'lucide-react';
import { PageHeader } from '../../shared/layout/PageHeader';
import { Button } from '../../shared/ui/Button';
import { AdminResourceTable, type AdminColumn } from '../components/AdminResourceTable';
import { useAdminResource } from '../lib/useAdminResource';
import { addPlatformAdmin, listPlatformAdmins, revokePlatformAdmin, type PlatformAdminDTO } from '../../lib/api/admin/platformAdmins';
import { cn } from '../../shared/utils/cn';

export function PlatformAdmins() {
  const { getToken } = useAuth();
  const fetchList = useCallback(() => getToken().then((t) => listPlatformAdmins(t)), [getToken]);
  const { items, isLoading, refresh } = useAdminResource(fetchList);
  const [newEmail, setNewEmail] = useState('');
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newEmail.trim()) return;
    setError(null);
    try {
      const token = await getToken();
      await addPlatformAdmin(token, newEmail.trim());
      setNewEmail('');
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add admin');
    }
  };

  const handleRevoke = async (admin: PlatformAdminDTO) => {
    if (!confirm(`Revoke admin access for ${admin.email}?`)) return;
    setBusyId(admin.id);
    setError(null);
    try {
      const token = await getToken();
      await revokePlatformAdmin(token, admin.id);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to revoke admin');
    } finally {
      setBusyId(null);
    }
  };

  const columns: AdminColumn<PlatformAdminDTO>[] = [
    { key: 'email', header: 'Email' },
    { key: 'added_by', header: 'Added by' },
    {
      key: 'is_active',
      header: 'Status',
      render: (row) => (
        <span
          className={cn(
            'inline-flex rounded-full border px-2.5 py-1 text-[11.5px] font-medium',
            row.is_active ? 'border-signal/50 text-signal' : 'border-ink-600 text-chalk-faint'
          )}
        >
          {row.is_active ? 'Active' : 'Revoked'}
        </span>
      )
    }
  ];

  return (
    <div>
      <PageHeader
        title="Platform admins"
        description="Who has full control access. New admins are added by email — no code or redeploy needed."
      />

      <form onSubmit={handleAdd} className="mb-6 flex items-end gap-3 rounded-2xl border border-ink-800 bg-ink-900 p-5">
        <div className="flex-1 space-y-1.5">
          <label htmlFor="new-admin-email" className="block text-[12.5px] font-medium text-chalk-dim">
            Add admin by email
          </label>
          <input
            id="new-admin-email"
            type="email"
            value={newEmail}
            onChange={(e) => setNewEmail(e.target.value)}
            placeholder="someone@crawlio.io"
            className="h-10 w-full rounded-lg border border-ink-700 bg-ink-950 px-3 text-[13.5px] text-chalk outline-none focus:border-signal/60"
          />
        </div>
        <Button type="submit" size="md">
          Add admin
        </Button>
      </form>
      {error && <p className="mb-4 text-[13px] text-ember">{error}</p>}

      <AdminResourceTable
        columns={columns}
        rows={items}
        isLoading={isLoading}
        getRowId={(row) => row.id}
        renderActions={(row) => (
          row.is_active && (
            <button
              type="button"
              onClick={() => handleRevoke(row)}
              disabled={busyId === row.id}
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-ink-700 text-chalk-dim hover:border-ember/50 hover:text-ember disabled:opacity-50"
              aria-label={`Revoke ${row.email}`}
            >
              <Trash2Icon className="h-3.5 w-3.5" />
            </button>
          )
        )}
      />
    </div>
  );
}
