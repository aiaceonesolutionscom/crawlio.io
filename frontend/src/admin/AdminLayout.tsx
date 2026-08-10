import React from 'react';
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useClerk } from '@clerk/clerk-react';
import {
  LayoutDashboardIcon,
  LogOutIcon,
  ShieldCheckIcon,
  SlidersHorizontalIcon,
  UsersIcon,
  Building2Icon,
  HistoryIcon,
  FlagIcon,
  SettingsIcon
} from 'lucide-react';
import { Logo } from '../shared/ui/Logo';
import { cn } from '../shared/utils/cn';
import { useAdminSession } from '../contexts/AdminSessionContext';

const NAV = [
  { to: '/admin', label: 'Dashboard', icon: LayoutDashboardIcon, end: true },
  { to: '/admin/workspaces', label: 'Workspaces', icon: Building2Icon, end: false },
  { to: '/admin/plan-configs', label: 'Plans & Limits', icon: SlidersHorizontalIcon, end: false },
  { to: '/admin/platform-admins', label: 'Platform Admins', icon: UsersIcon, end: false },
  { to: '/admin/audit-log', label: 'Audit Log', icon: HistoryIcon, end: false },
  { to: '/admin/feature-flags', label: 'Feature Flags', icon: FlagIcon, end: false },
  { to: '/admin/system-settings', label: 'System Settings', icon: SettingsIcon, end: false }
];

/** Entirely separate shell from the customer-facing tier layouts — visually
 * distinct so cross-tenant destructive actions never look like a normal
 * customer view. */
export function AdminLayout() {
  const { admin } = useAdminSession();
  const { signOut } = useClerk();
  const navigate = useNavigate();

  const handleLogout = () => {
    void signOut();
    navigate('/');
  };

  return (
    <div className="flex min-h-screen w-full bg-ink-950">
      <aside className="hidden w-[248px] shrink-0 border-r border-ember/30 bg-ink-900 lg:block">
        <div className="sticky top-0 flex h-screen flex-col">
          <div className="flex h-16 items-center gap-2 px-5">
            <Link to="/admin" aria-label="Crawlio admin">
              <Logo />
            </Link>
          </div>

          <div className="mx-3 mb-2 flex items-center gap-1.5 rounded-lg border border-ember/40 bg-ember/10 px-3 py-2">
            <ShieldCheckIcon className="h-3.5 w-3.5 text-ember" />
            <span className="font-mono text-[10.5px] uppercase tracking-[0.16em] text-ember">Admin mode</span>
          </div>

          <ul className="flex-1 space-y-1 px-3 py-3">
            {NAV.map((item) => (
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
              onClick={handleLogout}
              className="mt-2 flex w-full items-center gap-2 rounded-lg border border-ink-700 px-3 py-2 text-left text-[13px] text-chalk-dim hover:text-chalk"
            >
              <LogOutIcon className="h-3.5 w-3.5" />
              Log out
            </button>
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-40 flex h-12 items-center border-b border-ember/30 bg-ember/5 px-4 sm:px-6">
          <span className="font-mono text-[11px] uppercase tracking-[0.16em] text-ember">
            Platform admin — changes here affect real customer data across every workspace
          </span>
        </header>

        <main className="flex-1 px-4 py-6 sm:px-6 sm:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
