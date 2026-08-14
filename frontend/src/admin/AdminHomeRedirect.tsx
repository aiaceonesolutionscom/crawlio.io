import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAdminSession } from '../contexts/AdminSessionContext';

/** /admin entry point — bounces the signed-in admin to their own shell based on
 * role. Sub Admins with zero permissions still land on /admin/sub-admin and see
 * the "no permissions yet" empty state in the sidebar. */
export function AdminHomeRedirect() {
  const { admin, isLoaded } = useAdminSession();
  if (!isLoaded) return null;
  if (!admin) return <Navigate to="/app" replace />;
  if (admin.role === 'super_admin') return <Navigate to="/admin/super-admin" replace />;
  return <Navigate to="/admin/sub-admin" replace />;
}