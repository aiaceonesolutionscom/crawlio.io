import React, { useCallback, useState } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { ShieldCheckIcon, Trash2Icon } from 'lucide-react';
import { PageHeader } from '../../../shared/layout/PageHeader';
import { Button } from '../../../shared/ui/Button';
import { AdminResourceTable, type AdminColumn } from '../../components/AdminResourceTable';
import { useAdminResource } from '../../lib/useAdminResource';
import {
  addPlatformAdmin,
  grantAdminPermission,
  listAdminPermissions,
  listPlatformAdmins,
  revokeAdminPermission,
  revokePlatformAdmin,
  updatePlatformAdminRole,
  type AdminPermissionDTO,
  type PlatformAdminDTO
} from '../../../lib/api/admin/platformAdmins';
import { ADMIN_PERMISSIONS, ADMIN_ROLES } from '../../../shared/admin/permissions';
import { cn } from '../../../shared/utils/cn';

export function PlatformAdmins() {
  const { getToken } = useAuth();
  const fetchList = useCallback(() => getToken().then((t) => listPlatformAdmins(t)), [getToken]);
  const { items, isLoading, refresh } = useAdminResource(fetchList);
  const [newEmail, setNewEmail] = useState('');
  const [newRole, setNewRole] = useState<string>('sub_admin');
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [permissionsByAdmin, setPermissionsByAdmin] = useState<Record<string, AdminPermissionDTO[]>>({});
  const [expandedAdmin, setExpandedAdmin] = useState<string | null>(null);

  const loadPermissions = async (token: string | null, adminId: string) => {
    try {
      const perms = await listAdminPermissions(token, adminId);
      setPermissionsByAdmin((prev) => ({ ...prev, [adminId]: perms }));
    } catch {
      setPermissionsByAdmin((prev) => ({ ...prev, [adminId]: [] }));
    }
  };

  const handleToggleExpand = async (admin: PlatformAdminDTO) => {
    if (expandedAdmin === admin.id) {
      setExpandedAdmin(null);
      return;
    }
    setExpandedAdmin(admin.id);
    const token = await getToken();
    await loadPermissions(token, admin.id);
  };

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newEmail.trim()) return;
    setError(null);
    try {
      const token = await getToken();
      await addPlatformAdmin(token, newEmail.trim(), newRole);
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

  const handleToggleRole = async (admin: PlatformAdminDTO) => {
    const newRoleVal = admin.role === 'super_admin' ? 'sub_admin' : 'super_admin';
    setBusyId(admin.id);
    setError(null);
    try {
      const token = await getToken();
      await updatePlatformAdminRole(token, admin.id, newRoleVal);
      await refresh();
      await loadPermissions(token, admin.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update role');
    } finally {
      setBusyId(null);
    }
  };

  const handleTogglePermission = async (admin: PlatformAdminDTO, permission: string) => {
    setBusyId(`perm:${permission}`);
    setError(null);
    try {
      const token = await getToken();
      const granted = (permissionsByAdmin[admin.id] ?? []).some((p) => p.permission === permission);
      if (granted) {
        await revokeAdminPermission(token, admin.id, permission);
      } else {
        await grantAdminPermission(token, admin.id, permission);
      }
      await loadPermissions(token, admin.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update permission');
    } finally {
      setBusyId(null);
    }
  };

  const columns: AdminColumn<PlatformAdminDTO>[] = [
    { key: 'email', header: 'Email' },
    {
      key: 'role',
      header: 'Role',
      render: (row) => (
        <span
          className={cn(
            'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11.5px] font-medium',
            row.role === 'super_admin'
              ? 'border-ember/50 bg-ember/10 text-ember'
              : 'border-signal/50 bg-signal/10 text-signal'
          )}
        >
          {row.role === 'super_admin' && <ShieldCheckIcon className="h-3 w-3" />}
          {row.role === 'super_admin' ? 'Super Admin' : 'Sub Admin'}
        </span>
      )
    },
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
        description="Super Admins have full control. Sub Admins only get the permissions you grant them."
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
        <div className="w-48 space-y-1.5">
          <label htmlFor="new-admin-role" className="block text-[12.5px] font-medium text-chalk-dim">
            Role
          </label>
          <select
            id="new-admin-role"
            value={newRole}
            onChange={(e) => setNewRole(e.target.value)}
            className="h-10 w-full rounded-lg border border-ink-700 bg-ink-950 px-3 text-[13.5px] text-chalk outline-none focus:border-signal/60"
          >
            {ADMIN_ROLES.map((r) => (
              <option key={r.key} value={r.key}>
                {r.label}
              </option>
            ))}
          </select>
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
        onRowClick={handleToggleExpand}
        renderActions={(row) => (
          row.is_active && (
            <>
              <button
                type="button"
                onClick={() => handleToggleRole(row)}
                disabled={busyId === row.id}
                className="inline-flex h-8 items-center rounded-lg border border-ink-700 px-2.5 text-[12px] text-chalk-dim hover:border-signal/50 hover:text-signal disabled:opacity-50"
                title="Toggle Super/Sub Admin"
              >
                {row.role === 'super_admin' ? 'Make Sub' : 'Make Super'}
              </button>
              <button
                type="button"
                onClick={() => handleRevoke(row)}
                disabled={busyId === row.id}
                className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-ink-700 text-chalk-dim hover:border-ember/50 hover:text-ember disabled:opacity-50"
                aria-label={`Revoke ${row.email}`}
              >
                <Trash2Icon className="h-3.5 w-3.5" />
              </button>
            </>
          )
        )}
        renderExpanded={(row) =>
          expandedAdmin === row.id ? (
            <div className="px-6 py-4">
              {row.role === 'super_admin' ? (
                <p className="text-[13px] text-chalk-dim">
                  Super Admins implicitly hold every permission — no per-permission grants needed.
                </p>
              ) : (
                <div>
                  <p className="mb-3 text-[12.5px] font-medium text-chalk-dim">
                    Grant permissions for {row.email}
                  </p>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {ADMIN_PERMISSIONS.map((perm) => {
                      const granted = (permissionsByAdmin[row.id] ?? []).some(
                        (p) => p.permission === perm.key
                      );
                      const busy = busyId === `perm:${perm.key}`;
                      return (
                        <label
                          key={perm.key}
                          className={cn(
                            'flex cursor-pointer items-start gap-2.5 rounded-lg border px-3 py-2.5 transition-colors',
                            granted ? 'border-signal/50 bg-signal/5' : 'border-ink-700 hover:border-ink-600'
                          )}
                        >
                          <input
                            type="checkbox"
                            checked={granted}
                            disabled={busy}
                            onChange={() => handleTogglePermission(row, perm.key)}
                            className="mt-0.5 h-3.5 w-3.5 accent-signal"
                          />
                          <span className="text-[13px] text-chalk">{perm.label}</span>
                        </label>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          ) : null
        }
      />
    </div>
  );
}