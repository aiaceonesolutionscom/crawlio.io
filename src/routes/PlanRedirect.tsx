import React from 'react';
import { Navigate } from 'react-router-dom';
import { useSession } from '../contexts/SessionContext';

/** Resolves bare /app to the session's own tier root. */
export function PlanRedirect() {
  const { user, isLoaded } = useSession();
  if (!isLoaded) return null;
  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to={`/app/${user.workspace.plan}`} replace />;
}
