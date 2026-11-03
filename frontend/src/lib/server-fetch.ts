import { notFound } from 'next/navigation';
import type { ContractSummary, Clause, Obligation, RiskFlag, GraphSnapshot } from '@/types';

/**
 * Server-side fetch helpers for pages. These run in the Next.js runtime, so
 * they call the backend directly via BACKEND_URL (no /api proxy). The bearer
 * token is NOT available server-side (it lives in the browser), so these are
 * used only when backend auth is disabled (the default demo mode) or for
 * public reads. When auth is enabled, pages fall back to client-side hooks.
 */

const BASE = (process.env.BACKEND_URL || 'http://127.0.0.1:8010').replace(/\/$/, '');

async function get<T>(path: string, revalidate = 60): Promise<T> {
  const res = await fetch(`${BASE}/api/v1/${path}`, {
    cache: 'force-cache',
    next: { revalidate },
  });
  if (!res.ok) {
    // Pages treat backend errors as "not available" rather than crashing the
    // whole page — the client-side hooks show the real error state.
    throw Object.assign(new Error(`Backend ${res.status} for ${path}`), { status: res.status });
  }
  return (await res.json()) as T;
}

export const fetchSummary = (contractId: string) => get<ContractSummary>(`contracts/${contractId}/summary`);
export const fetchClauses = (contractId: string) => get<{ clauses: Clause[] }>(`contracts/${contractId}/clauses`);
export const fetchObligations = (contractId: string) => get<{ obligations: Obligation[] }>(`contracts/${contractId}/obligations`);
export const fetchRisks = (contractId: string) => get<{ risks: RiskFlag[] }>(`contracts/${contractId}/risks`);
export const fetchGraph = (contractId: string) => get<GraphSnapshot>(`graph/${contractId}`);
export const fetchJob = (jobId: string) => get<import('@/types').JobInfo>(`jobs/${jobId}`);

export { notFound };
