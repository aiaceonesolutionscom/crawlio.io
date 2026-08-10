import React from 'react';
import { Navigate } from 'react-router-dom';
import { useSession } from '../contexts/SessionContext';
import type { PlanId } from '../types';

interface Props {
  tier: PlanId;
  children: React.ReactNode;
}

/** Bounces a session onto its own tier root if the URL's tier doesn't match workspace.plan — defense-in-depth alongside the backend's independent 403s, never the only guard. */
export function RequirePlan({ tier, children }: Props) {
  const { user, isLoaded } = useSession();
  if (!isLoaded) return null;
  if (!user) return null;
  if (!user.workspace.planSelected) return <Navigate to="/select-plan" replace />;
  if (user.workspace.plan !== tier) {
    return <Navigate to={`/app/${user.workspace.plan}`} replace />;
  }
  return <>{children}</>;
}
