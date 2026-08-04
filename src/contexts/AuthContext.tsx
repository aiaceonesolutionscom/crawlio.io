import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { PLAN_LIMITS } from '../data/plans';
import type { PlanId, User } from '../types';

interface AuthContextValue {
  user: User | null;
  isPending: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  signup: (input: {name: string;email: string;password: string;plan: PlanId;}) => Promise<void>;
  logout: () => void;
  changePlan: (plan: PlanId) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function workspaceNameFor(email: string): string {
  const domain = email.split('@')[1] ?? 'crawlio.io';
  const base = domain.split('.')[0] ?? 'crawlio';
  return `${base.charAt(0).toUpperCase()}${base.slice(1)} Workspace`;
}

/** Simulates the backend provisioning pipeline: create workspace, seed defaults, apply plan quotas. */
function provisionWorkspace(name: string, email: string, plan: PlanId): User {
  const limits = PLAN_LIMITS[plan];
  return {
    id: `usr_${Math.random().toString(36).slice(2, 10)}`,
    name,
    email,
    role: 'Owner',
    workspace: {
      name: workspaceNameFor(email),
      plan,
      leadsUsed: plan === 'free' ? 214 : plan === 'pro' ? 3128 : 41903,
      leadQuota: limits.leads,
      seatsUsed: plan === 'free' ? 1 : 4,
      seatQuota: limits.seats,
      createdAt: new Date().toISOString()
    }
  };
}

const wait = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

export function AuthProvider({ children }: {children: React.ReactNode;}) {
  const [user, setUser] = useState<User | null>(null);
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const login = useCallback(async (email: string, password: string) => {
    setIsPending(true);
    setError(null);
    try {
      await wait(700);
      if (password.length < 6) {
        throw new Error('That password looks too short. Try at least 6 characters.');
      }
      setUser(provisionWorkspace(email.split('@')[0] ?? 'There', email, 'pro'));
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Something went wrong.';
      setError(message);
      throw e;
    } finally {
      setIsPending(false);
    }
  }, []);

  const signup = useCallback<AuthContextValue['signup']>(async ({ name, email, password, plan }) => {
    setIsPending(true);
    setError(null);
    try {
      await wait(900);
      if (password.length < 6) {
        throw new Error('Password must be at least 6 characters.');
      }
      setUser(provisionWorkspace(name, email, plan));
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Something went wrong.';
      setError(message);
      throw e;
    } finally {
      setIsPending(false);
    }
  }, []);

  const logout = useCallback(() => {
    setUser(null);
    setError(null);
  }, []);

  const changePlan = useCallback((plan: PlanId) => {
    setUser((prev) => {
      if (!prev) return prev;
      const limits = PLAN_LIMITS[plan];
      return {
        ...prev,
        workspace: { ...prev.workspace, plan, leadQuota: limits.leads, seatQuota: limits.seats }
      };
    });
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ user, isPending, error, login, signup, logout, changePlan }),
    [user, isPending, error, login, signup, logout, changePlan]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}