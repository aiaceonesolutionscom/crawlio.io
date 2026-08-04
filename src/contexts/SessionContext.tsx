import React, { createContext, useContext, useMemo } from 'react';
import { useAuth as useClerkAuth, useClerk, useUser } from '@clerk/clerk-react';
import { PLAN_LIMITS } from '../data/plans';
import type { User } from '../types';

interface SessionContextValue {
  user: User | null;
  isLoaded: boolean;
  logout: () => void;
}

const SessionContext = createContext<SessionContextValue | null>(null);

/**
 * Wraps Clerk's identity state and shapes it into the same `User` shape the
 * tier pages already consume. workspace.plan is hardcoded 'free' until Phase 4
 * wires GET /workspaces/me — that's the only thing that changes here later.
 */
export function SessionProvider({ children }: {children: React.ReactNode;}) {
  const { isLoaded, isSignedIn } = useClerkAuth();
  const { user: clerkUser } = useUser();
  const { signOut } = useClerk();

  const user = useMemo<User | null>(() => {
    if (!isSignedIn || !clerkUser) return null;
    const limits = PLAN_LIMITS.free;
    const displayName =
    clerkUser.fullName ??
    clerkUser.username ??
    clerkUser.primaryEmailAddress?.emailAddress ??
    'There';

    return {
      id: clerkUser.id,
      name: displayName,
      email: clerkUser.primaryEmailAddress?.emailAddress ?? '',
      role: 'Owner',
      workspace: {
        name: `${clerkUser.firstName ?? clerkUser.username ?? 'My'} Workspace`,
        plan: 'free',
        leadsUsed: 0,
        leadQuota: limits.leads,
        seatsUsed: 1,
        seatQuota: limits.seats,
        createdAt: clerkUser.createdAt?.toISOString() ?? new Date().toISOString()
      }
    };
  }, [isSignedIn, clerkUser]);

  const value = useMemo<SessionContextValue>(
    () => ({ user, isLoaded, logout: () => void signOut() }),
    [user, isLoaded, signOut]
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionContextValue {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error('useSession must be used inside SessionProvider');
  return ctx;
}
