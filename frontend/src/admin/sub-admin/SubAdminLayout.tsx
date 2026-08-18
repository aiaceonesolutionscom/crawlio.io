import React from 'react';
import { Link, NavLink, Outlet } from 'react-router-dom';
import {
  LayoutDashboardIcon,
  LogOutIcon,
  ShieldCheckIcon,
  Building2Icon,
  HistoryIcon,
  KeyRoundIcon
} from 'lucide-react';
import { Logo } from '../../shared/ui/Logo';
import { cn } from '../../shared/utils/cn';
import { useAdminSession } from '../../contexts/AdminSessionContext';

const NAV = [
  { to: '/admin/sub-admin', label: 'Dashboard', icon: LayoutDashboardIcon, end: true, perm: 'dashboard.read' },
  { to: '/admin/sub-admin/workspaces', label: 'Workspaces', icon: Building2Icon, end: false, perm: 'workspaces.read' },
  { to: '/admin/sub-admin/audit-log', label: 'Audit Log', icon: HistoryIcon, end: false, perm: 'audit.read' },
  { to: '/admin/sub-admin/integrations', label: 'API Keys & Integrations', icon: KeyRoundIcon, end: false, perm: 'integrations.read' }
];

/** Sub Admin shell — only the sections the Super Admin explicitly granted via
 * permissions are shown. Nav items are filtered by the current admin's
 * effective permission set; the same permissions are enforced server-side. */
export function SubAdminLayout() {
  const { admin, logout } = useAdminSession();

  const permissions = new Set(admin?.permissions ?? []);
  const visibleNav = NAV.filter((item) => permissions.has(item.perm));

  return (
    <div className="flex min-h-screen w-full bg-ink-950">
      <aside className="fixed top-0 left-0 z-40 h-screen w-[248px] shrink-0 border-r border-ember/30 bg-ink-900 lg:block">
        <div className="h-screen flex flex-col overflow-y-auto">
          <div className="flex h-16 items-center gap-2 px-5">
            <Link to="/admin/sub-admin" aria-label="Crawlio admin">
              <Logo />
            </Link>
          </div>

          <div className="mx-3 mb-2 flex items-center gap-1.5 rounded-lg border border-ember/40 bg-ember/10 px-3 py-2">
            <ShieldCheckIcon className="h-3.5 w-3.5 text-ember" />
            <span className="font-mono text-[10.5px] uppercase tracking-[0.16em] text-ember">Sub Admin</span>
          </div>

          <ul className="flex-1 space-y-1 px-3 py-3">
            {visibleNav.length === 0 && (
              <li className="px-3 py-2 text-[12.5px] text-chalk-faint">
                No permissions granted yet. Ask a Super Admin to grant you access.
              </li>
            )}
            {visibleNav.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) =>
                    cn(
                      'flex items-center gap-3 rounded-lg px-3 py-2.5 text-[14px] transition-colors',
                      isActive ? 'bg-ink-800 text-chalk' : 'text-chalk-dim hover:bg-ink-850 hover:text-chalk'
                    )
                  }
                >
                  <item.icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                  <span className="flex-1">{item.label}</span>
                </NavLink>
              </li>
            ))}
          </ul>

          <div className="border-t border-ink-850 p-4">
            <p className="truncate text-[12.5px] text-chalk-faint">{admin?.email}</p>
            <button
              type="button"
              onClick={logout}
              className="mt-2 flex w-full items-center gap-2 rounded-lg border border-ink-700 px-3 py-2 text-left text-[13px] text-chalk-dim hover:text-chalk"
            >
              <LogOutIcon className="h-3.5 w-3.5" />
              Log out
            </button>
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col ml-[248px]">
        <header className="sticky top-0 z-40 flex h-12 items-center border-b border-ember/30 bg-ember/5 px-4 sm:px-6 ml-[248px]">
          <span className="font-mono text-[11px] uppercase tracking-[0.16em] text-ember">
            Sub Admin — limited access, only what your Super Admin granted
          </span>
        </header>

        <main className="flex-1 px-4 py-6 sm:px-6 sm:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}