'use client';

import { useQuery } from '@tanstack/react-query';
import { contractsApi, jobsApi, graphApi } from '@/lib/api';

export function useContractSummary(contractId: string | null | undefined) {
  return useQuery({
    queryKey: ['contract', contractId, 'summary'],
    queryFn: ({ signal }) => contractsApi.summary(contractId as string, signal),
    enabled: !!contractId,
    retry: (f, e) => {
      const s = (e as { status?: number })?.status;
      return !(s && s >= 400 && s < 500) && f < 2;
    },
  });
}

export function useClauses(contractId: string | null | undefined) {
  return useQuery({
    queryKey: ['contract', contractId, 'clauses'],
    queryFn: ({ signal }) => contractsApi.clauses(contractId as string, signal),
    enabled: !!contractId,
  });
}

export function useObligations(contractId: string | null | undefined) {
  return useQuery({
    queryKey: ['contract', contractId, 'obligations'],
    queryFn: ({ signal }) => contractsApi.obligations(contractId as string, signal),
    enabled: !!contractId,
  });
}

export function useRisks(contractId: string | null | undefined) {
  return useQuery({
    queryKey: ['contract', contractId, 'risks'],
    queryFn: ({ signal }) => contractsApi.risks(contractId as string, signal),
    enabled: !!contractId,
  });
}

export function useGraph(contractId: string | null | undefined) {
  return useQuery({
    queryKey: ['graph', contractId],
    queryFn: ({ signal }) => graphApi.get(contractId as string, signal),
    enabled: !!contractId,
  });
}

/** Recent contracts (jobs with results). Used by the landing page. */
export function useRecentContracts() {
  return useQuery({
    queryKey: ['recent-contracts'],
    queryFn: ({ signal }) => jobsApi.list(signal),
    staleTime: 15_000,
    retry: 1,
  });
}
