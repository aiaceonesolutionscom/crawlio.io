import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiFetch } from '../lib/api/client';

const ADMIN_TOKEN_KEY = 'crawlio_admin_token';

export interface WhoamiDTO {
  email: string;
  role: string;
  is_super_admin: boolean;
  permissions: string[];
}

interface AdminSessionContextValue {
  admin: WhoamiDTO | null;
  isLoaded: boolean;
  logout: () => void;
}

const AdminSessionContext = createContext<AdminSessionContextValue | null>(null);

export function getAdminToken(): string | null {
  return localStorage.getItem(ADMIN_TOKEN_KEY);
}

export function AdminSessionProvider({ children }: { children: React.ReactNode }) {
  const [admin, setAdmin] = useState<WhoamiDTO | null>(null);
  const [isLoaded, setIsLoaded] = useState(false);
  const navigate = useNavigate();

  const loadAdmin = useCallback(async () => {
    const token = getAdminToken();
    if (!token) {
      setAdmin(null);
      setIsLoaded(true);
      return;
    }
    try {
      const who = await apiFetch<WhoamiDTO>('/api/v1/admin/whoami', token);
      setAdmin(who);
    } catch {
      localStorage.removeItem(ADMIN_TOKEN_KEY);
      setAdmin(null);
    } finally {
      setIsLoaded(true);
    }
  }, []);

  useEffect(() => {
    loadAdmin();
  }, [loadAdmin]);

  const logout = useCallback(() => {
    localStorage.removeItem(ADMIN_TOKEN_KEY);
    setAdmin(null);
    navigate('/admin/login');
  }, [navigate]);

  return (
    <AdminSessionContext.Provider value={{ admin, isLoaded, logout }}>
      {children}
    </AdminSessionContext.Provider>
  );
}

export function useAdminSession() {
  const ctx = useContext(AdminSessionContext);
  if (!ctx) throw new Error('useAdminSession must be used within AdminSessionProvider');
  return ctx;
}
