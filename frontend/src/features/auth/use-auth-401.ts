'use client';

import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';

/**
 * Global 401 handler: when the backend says the token is no longer valid,
 * clear it and send the user to /login (preserving the current path).
 * Runs once at provider level, so per-query logic stays clean.
 */
export function useAuth401Handler() {
  const qc = useQueryClient();

  useEffect(() => {
    const handler = (event: Event) => {
      const status = (event as CustomEvent<{ status?: number }>).detail?.status;
      if (status !== 401) return;
      try {
        window.localStorage.removeItem(process.env.AUTH_STORAGE_KEY || 'bharatcontract.token');
      } catch {
        /* ignore */
      }
      const path = window.location.pathname;
      if (path !== '/login') {
        window.location.href = `/login?next=${encodeURIComponent(path)}`;
      }
    };
    window.addEventListener('bharatcontract:unauthorized', handler);
    return () => window.removeEventListener('bharatcontract:unauthorized', handler);
  }, [qc]);
}

/** Fire the 401 event (called from API layer on a 401). */
export function emitUnauthorized(status: number) {
  if (typeof window === 'undefined' || status !== 401) return;
  window.dispatchEvent(new CustomEvent('bharatcontract:unauthorized', { detail: { status } }));
}
