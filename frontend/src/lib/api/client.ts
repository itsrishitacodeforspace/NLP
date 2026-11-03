import { ApiError } from './errors';
import { getToken } from './token-store';

/** Base URL for the backend. In dev the Next.js rewrite proxies /api -> backend,
 * so we use same-origin "/api/...". Set BACKEND_URL to call cross-origin directly. */
const BASE = (process.env.BACKEND_URL || '').replace(/\/$/, '');

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  body?: unknown;
  formData?: FormData;
  signal?: AbortSignal;
  /** When true, never attach the bearer token (used for /token itself). */
  noAuth?: boolean;
}

export async function apiRequest<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, formData, signal, noAuth } = opts;

  const headers: Record<string, string> = {};
  if (!formData) headers['Content-Type'] = 'application/json';
  const token = noAuth ? null : getToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const url = `${BASE}/api/v1/${path.replace(/^\/+/, '')}`;
  let res: Response;
  try {
    res = await fetch(url, {
      method,
      headers,
      body: formData ? formData : body === undefined ? undefined : JSON.stringify(body),
      signal,
    });
  } catch (e) {
    if ((e as Error).name === 'AbortError') throw e;
    throw new ApiError(0, 'Cannot reach the backend. Is the API server running?');
  }

  if (res.status === 204) return undefined as T;

  let data: unknown = null;
  const text = await res.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }

  if (!res.ok) {
    const detail =
      (data && typeof data === 'object' && 'detail' in data && (data as { detail: unknown }).detail) ||
      res.statusText ||
      `Request failed (${res.status})`;
    if (res.status === 401 && typeof window !== 'undefined' && !noAuth) {
      window.dispatchEvent(new CustomEvent('bharatcontract:unauthorized', { detail: { status: 401 } }));
    }
    throw new ApiError(res.status, typeof detail === 'string' ? detail : JSON.stringify(detail));
  }

  return data as T;
}
