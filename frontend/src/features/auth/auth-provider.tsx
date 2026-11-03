'use client';

import * as React from 'react';
import { useQuery } from '@tanstack/react-query';
import { authApi } from '@/lib/api';
import { getStoredUser, saveToken, clearToken } from '@/lib/api/token-store';
import type { UserInfo } from '@/types';

interface AuthContextValue {
  /** Resolved identity (live /me when a token exists, else stored user). */
  user: UserInfo | null;
  /** True when the backend reports auth_enabled=false (everyone is anonymous). */
  backendAuthEnabled: boolean;
  /** True when the backend requires auth. */
  requiresAuth: boolean;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const Ctx = React.createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const stored = getStoredUser();
  const hasToken = stored !== null;

  // Hit /me to learn the real backend auth state and resolve identity.
  const me = useQuery({
    queryKey: ['me'],
    queryFn: ({ signal }) => authApi.me(signal),
    // Always try: when auth is disabled the backend returns anonymous admin.
    staleTime: 60_000,
    retry: 1,
  });

  const backendAuthEnabled = me.data ? !me.data.authenticated : false;
  const requiresAuth = backendAuthEnabled;

  // If a token exists but /me fails (expired/invalid), clear it.
  React.useEffect(() => {
    if (hasToken && me.isError) {
      const status = (me.error as { status?: number })?.status;
      if (status === 401) clearToken();
    }
  }, [hasToken, me.isError, me.error]);

  const user: UserInfo | null = React.useMemo(() => {
    if (me.data) return me.data;
    if (stored) return { username: stored.username, role: stored.role, authenticated: true };
    return null;
  }, [me.data, stored]);

  const login = React.useCallback(async (username: string, password: string) => {
    const res = await authApi.login(username, password);
    saveToken({
      token: res.access_token,
      username: res.username,
      role: res.role,
      expiresAt: res.expires_in ? Date.now() + res.expires_in * 1000 : null,
    });
    await me.refetch();
  }, [me]);

  const logout = React.useCallback(() => {
    clearToken();
    me.refetch();
  }, [me]);

  const value: AuthContextValue = {
    user,
    backendAuthEnabled,
    requiresAuth,
    loading: me.isLoading,
    login,
    logout,
  };

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = React.useContext(Ctx);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
