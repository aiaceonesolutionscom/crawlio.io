import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAdminSession } from '../contexts/AdminSessionContext';

/** Bounces a signed-in-but-not-admin user back to their normal dashboard (not
 * /login — they *are* authenticated, just not authorized for /admin). */
export function RequireSuperAdmin({ children }: { children: React.ReactNode }) {
  const { admin, isLoaded } = useAdminSession();
  if (!isLoaded) return null;
  if (!admin) return <Navigate to="/app" replace />;
  return <>{children}</>;
}
