import React, { createContext, useContext, useEffect, useState } from 'react';
import { useAuth as useClerkAuth } from '@clerk/clerk-react';
import { ApiError } from '../lib/api/client';
import { getWhoami, type WhoamiDTO } from '../lib/api/admin/whoami';

// Deliberately separate from SessionContext: admin identity (platform_admins)
// is orthogonal to workspace identity, and hitting /admin must never trigger
// SessionContext's opportunistic create-workspace flow.
interface AdminSessionContextValue {
  admin: WhoamiDTO | null;
  isLoaded: boolean;
}

const AdminSessionContext = createContext<AdminSessionContextValue | null>(null);

export function AdminSessionProvider({ children }: { children: React.ReactNode }) {
  const { isLoaded: clerkLoaded, isSignedIn, getToken } = useClerkAuth();
  const [admin, setAdmin] = useState<WhoamiDTO | null>(null);
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    if (!clerkLoaded) return;
    if (!isSignedIn) {
      setAdmin(null);
      setIsLoaded(true);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const token = await getToken();
        const who = await getWhoami(token);
        if (!cancelled) setAdmin(who);
      } catch (e) {
        if (!(e instanceof ApiError && e.status === 403)) {
          console.error('Failed to resolve admin session', e);
        }
        if (!cancelled) setAdmin(null);
      } finally {
        if (!cancelled) setIsLoaded(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [clerkLoaded, isSignedIn, getToken]);

  return <AdminSessionContext.Provider value={{ admin, isLoaded }}>{children}</AdminSessionContext.Provider>;
}

export function useAdminSession() {
  const ctx = useContext(AdminSessionContext);
  if (!ctx) throw new Error('useAdminSession must be used within AdminSessionProvider');
  return ctx;
}
