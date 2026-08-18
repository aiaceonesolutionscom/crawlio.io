import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAdminSession } from '../contexts/AdminSessionContext';

export function RequireAdmin({ children }: { children: React.ReactNode }) {
  const { admin, isLoaded } = useAdminSession();
  if (!isLoaded) return null;
  if (!admin) return <Navigate to="/admin/login" replace />;
  return <>{children}</>;
}
