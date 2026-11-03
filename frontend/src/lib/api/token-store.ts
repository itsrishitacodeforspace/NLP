import { ApiError } from './errors';

/**
 * Token store. Bearer tokens only (the backend's only auth mechanism).
 *
 * Security note (documented trade-off, see README §Auth): the token is kept in
 * `localStorage` so the SPA can attach it to fetch calls. This is readable by
 * JS in the page (XSS risk) — the backend remains authoritative for
 * authorization, and frontend role checks are UX only. A cookie + CSRF scheme
 * would be the production hardening; it is NOT implemented here because the
 * backend does not support Set-Cookie auth.
 */
const KEY = process.env.AUTH_STORAGE_KEY || 'bharatcontract.token';

export interface StoredToken {
  token: string;
  username: string;
  role: string;
  /** epoch ms when the token expires (best-effort from backend expires_in). */
  expiresAt: number | null;
}

export function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as StoredToken;
    if (parsed.expiresAt && Date.now() > parsed.expiresAt) {
      clearToken();
      return null;
    }
    return parsed.token;
  } catch {
    return null;
  }
}

export function getStoredUser(): Pick<StoredToken, 'username' | 'role'> | null {
  const t = getToken();
  if (!t) return null;
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as StoredToken;
    return { username: parsed.username, role: parsed.role };
  } catch {
    return null;
  }
}

export function saveToken(t: StoredToken): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(KEY, JSON.stringify(t));
  } catch {
    /* storage full / disabled — auth simply won't persist */
  }
}

export function clearToken(): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
}
