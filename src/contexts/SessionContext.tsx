import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useAuth as useClerkAuth, useClerk, useUser } from '@clerk/clerk-react';
import { ApiError } from '../lib/api/client';
import { createWorkspace, getMyWorkspace, updateWorkspacePlan, type WorkspaceDTO } from '../lib/api/workspaces';
import type { PlanId, User } from '../types';

interface SessionContextValue {
  user: User | null;
  isLoaded: boolean;
  logout: () => void;
  changePlan: (plan: PlanId) => Promise<void>;
}

const SessionContext = createContext<SessionContextValue | null>(null);

/**
 * Wraps Clerk's identity state and a real workspace fetched from the backend,
 * shaped into the `User` type the tier pages already consume. On first /app
 * visit for a user with no workspace yet (fresh signup), one is auto-created
 * as Free — this stands in for a dedicated post-signup provisioning step
 * since Clerk's prebuilt <SignUp> doesn't give us a mid-flow hook.
 */
export function SessionProvider({ children }: {children: React.ReactNode;}) {
  const { isLoaded: clerkLoaded, isSignedIn, getToken } = useClerkAuth();
  const { user: clerkUser } = useUser();
  const { signOut } = useClerk();
  const [workspace, setWorkspace] = useState<WorkspaceDTO | null>(null);
  const [workspaceLoaded, setWorkspaceLoaded] = useState(false);

  const loadWorkspace = useCallback(async () => {
    if (!isSignedIn) {
      setWorkspace(null);
      setWorkspaceLoaded(true);
      return;
    }
    const token = await getToken();
    try {
      const ws = await getMyWorkspace(token);
      setWorkspace(ws);
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        const name = `${clerkUser?.firstName ?? clerkUser?.username ?? 'My'} Workspace`;
        const ws = await createWorkspace(
          token,
          name,
          clerkUser?.primaryEmailAddress?.emailAddress,
          clerkUser?.fullName ?? clerkUser?.firstName ?? undefined
        );
        setWorkspace(ws);
      } else {
        throw e;
      }
    } finally {
      setWorkspaceLoaded(true);
    }
  }, [isSignedIn, getToken, clerkUser]);

  useEffect(() => {
    if (clerkLoaded) void loadWorkspace();
  }, [clerkLoaded, isSignedIn, loadWorkspace]);

  const changePlan = useCallback(
    async (plan: PlanId) => {
      if (!workspace) return;
      const token = await getToken();
      const updated = await updateWorkspacePlan(token, workspace.id, plan);
      setWorkspace(updated);
    },
    [workspace, getToken]
  );

  const user = useMemo<User | null>(() => {
    if (!isSignedIn || !clerkUser || !workspace) return null;
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
        name: workspace.name,
        plan: workspace.plan,
        leadsUsed: 0,
        leadQuota: workspace.lead_quota,
        seatsUsed: 1,
        seatQuota: workspace.seat_quota,
        createdAt: workspace.created_at
      }
    };
  }, [isSignedIn, clerkUser, workspace]);

  const isLoaded = clerkLoaded && (!isSignedIn || workspaceLoaded);

  const value = useMemo<SessionContextValue>(
    () => ({ user, isLoaded, logout: () => void signOut(), changePlan }),
    [user, isLoaded, signOut, changePlan]
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionContextValue {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error('useSession must be used inside SessionProvider');
  return ctx;
}
