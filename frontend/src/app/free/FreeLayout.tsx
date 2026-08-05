import React, { useState } from 'react';
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom';
import { ChevronDownIcon, LogOutIcon, MenuIcon, XIcon } from 'lucide-react';
import { Logo } from '../../shared/ui/Logo';
import { Button } from '../../shared/ui/Button';
import { UpgradeModal } from '../../shared/ui/UpgradeModal';
import { useSession } from '../../contexts/SessionContext';
import { cn } from '../../shared/utils/cn';
import { NAV } from './nav';

export function FreeLayout() {
  const { user, logout } = useSession();
  const navigate = useNavigate();
  const [navOpen, setNavOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [upgradeOpen, setUpgradeOpen] = useState(false);

  if (!user) return null;
  const { workspace } = user;

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  const sidebar =
  <nav aria-label="Dashboard" className="flex h-full flex-col">
      <div className="flex h-16 items-center px-5">
        <Link to="/app/free" aria-label="Crawlio dashboard">
          <Logo />
        </Link>
      </div>

      <ul className="flex-1 space-y-1 px-3 py-3">
        {NAV.map((item) =>
        <li key={item.to}>
            <NavLink
            to={item.to}
            end={item.end}
            onClick={() => setNavOpen(false)}
            className={({ isActive }) =>
            cn(
              'flex items-center gap-3 rounded-lg px-3 py-2.5 text-[14px] transition-colors',
              isActive ? 'bg-ink-800 text-chalk' : 'text-chalk-dim hover:bg-ink-850 hover:text-chalk'
            )
            }>

              <item.icon className="h-4 w-4 shrink-0" aria-hidden="true" />
              <span className="flex-1">{item.label}</span>
              {item.locked &&
            <span className="rounded bg-ink-800 px-1.5 py-0.5 font-mono text-[10px] uppercase text-chalk-faint">
                  Pro
                </span>
            }
            </NavLink>
          </li>
        )}
      </ul>

      <div className="border-t border-ink-850 p-4">
        <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-chalk-faint">Current plan</p>
        <p className="mt-1.5 font-display text-[16px] font-semibold text-chalk">Free</p>
        <Button size="sm" className="mt-3 w-full" onClick={() => setUpgradeOpen(true)}>
          Upgrade plan
        </Button>
      </div>
    </nav>;


  return (
    <div className="flex min-h-screen w-full bg-ink-950">
      <aside className="hidden w-[248px] shrink-0 border-r border-ink-850 bg-ink-900 lg:block">
        <div className="sticky top-0 h-screen">{sidebar}</div>
      </aside>

      {navOpen &&
      <div className="fixed inset-0 z-50 lg:hidden">
          <button
          type="button"
          aria-label="Close navigation"
          onClick={() => setNavOpen(false)}
          className="absolute inset-0 bg-ink-950/80" />

          <div className="absolute inset-y-0 left-0 w-[264px] border-r border-ink-800 bg-ink-900">{sidebar}</div>
        </div>
      }

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-40 flex h-16 items-center gap-3 border-b border-ink-850 bg-ink-950/90 px-4 backdrop-blur-xl sm:px-6">
          <button
            type="button"
            onClick={() => setNavOpen(true)}
            aria-label="Open navigation"
            className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-ink-700 text-chalk lg:hidden">

            <MenuIcon className="h-5 w-5" />
          </button>

          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h1 className="truncate font-display text-[15px] font-semibold tracking-tight text-chalk">
                {workspace.name}
              </h1>
              <span className="rounded bg-ink-800 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-chalk-dim">
                Free
              </span>
            </div>
          </div>

          <div className="relative">
            <button
              type="button"
              onClick={() => setMenuOpen((v) => !v)}
              aria-expanded={menuOpen}
              className="flex items-center gap-2 rounded-lg border border-ink-700 bg-ink-900 py-1.5 pl-1.5 pr-2.5 text-[13px] text-chalk hover:border-ink-600">

              <span
                aria-hidden="true"
                className="flex h-7 w-7 items-center justify-center rounded-md bg-ink-800 font-display text-[12px] font-semibold text-signal">

                {user.name.slice(0, 1).toUpperCase()}
              </span>
              <span className="hidden max-w-[120px] truncate sm:block">{user.name}</span>
              <ChevronDownIcon className="h-3.5 w-3.5 text-chalk-faint" />
            </button>

            {menuOpen &&
            <div className="absolute right-0 top-[calc(100%+8px)] w-60 overflow-hidden rounded-xl border border-ink-700 bg-ink-900 shadow-2xl">
                <div className="border-b border-ink-850 px-4 py-3">
                  <p className="truncate text-[13.5px] font-medium text-chalk">{user.name}</p>
                  <p className="truncate text-[12.5px] text-chalk-faint">{user.email}</p>
                  <p className="mt-1 font-mono text-[11px] text-chalk-faint">Role: {user.role}</p>
                </div>
                <Link
                to="/app/free/settings"
                onClick={() => setMenuOpen(false)}
                className="block px-4 py-2.5 text-[13.5px] text-chalk-dim hover:bg-ink-850 hover:text-chalk">

                  Workspace settings
                </Link>
                <button
                type="button"
                onClick={handleLogout}
                className="flex w-full items-center gap-2 border-t border-ink-850 px-4 py-2.5 text-left text-[13.5px] text-chalk-dim hover:bg-ink-850 hover:text-chalk">

                  <LogOutIcon className="h-3.5 w-3.5" />
                  Log out
                </button>
              </div>
            }
          </div>
        </header>

        <main className="flex-1 px-4 py-6 sm:px-6 sm:py-8">
          <Outlet context={{ openUpgrade: () => setUpgradeOpen(true) }} />
        </main>
      </div>

      <UpgradeModal open={upgradeOpen} onClose={() => setUpgradeOpen(false)} />

      {menuOpen &&
      <button
        type="button"
        aria-hidden="true"
        tabIndex={-1}
        onClick={() => setMenuOpen(false)}
        className="fixed inset-0 z-30 cursor-default" />

      }
    </div>);

}
