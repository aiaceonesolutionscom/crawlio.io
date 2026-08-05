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
  refreshWorkspace: () => Promise<void>;
}

const SessionContext = createContext<SessionContextValue | null>(null);

function createLocalWorkspace(clerkUser: ReturnType<typeof useUser>['user']): WorkspaceDTO {
  return {
    id: 'local-' + Date.now(),
    name: `${clerkUser?.firstName ?? clerkUser?.username ?? 'My'} Workspace`,
    plan: 'free',
    lead_quota: 500,
    seat_quota: 1,
    leads_used: 0,
    seats_used: 1,
    created_at: new Date().toISOString(),
  };
}

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
        try {
          const name = `${clerkUser?.firstName ?? clerkUser?.username ?? 'My'} Workspace`;
          const ws = await createWorkspace(
            token,
            name,
            clerkUser?.primaryEmailAddress?.emailAddress,
            clerkUser?.fullName ?? clerkUser?.firstName ?? undefined
          );
          setWorkspace(ws);
        } catch {
          setWorkspace(createLocalWorkspace(clerkUser));
        }
      } else {
        setWorkspace(createLocalWorkspace(clerkUser));
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
      try {
        const token = await getToken();
        const updated = await updateWorkspacePlan(token, workspace.id, plan);
        setWorkspace(updated);
      } catch {
        setWorkspace({ ...workspace, plan });
      }
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
        leadsUsed: workspace.leads_used,
        leadQuota: workspace.lead_quota,
        seatsUsed: workspace.seats_used,
        seatQuota: workspace.seat_quota,
        createdAt: workspace.created_at
      }
    };
  }, [isSignedIn, clerkUser, workspace]);

  const isLoaded = clerkLoaded && (!isSignedIn || workspaceLoaded);

  const value = useMemo<SessionContextValue>(
    () => ({ user, isLoaded, logout: () => void signOut(), changePlan, refreshWorkspace: loadWorkspace }),
    [user, isLoaded, signOut, changePlan, loadWorkspace]
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionContextValue {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error('useSession must be used inside SessionProvider');
  return ctx;
}
