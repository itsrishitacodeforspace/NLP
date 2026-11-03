'use client';

import { useQuery } from '@tanstack/react-query';
import { jobsApi } from '@/lib/api';
import type { JobInfo, JobStatus } from '@/types';

export const TERMINAL_STATUSES: JobStatus[] = ['succeeded', 'failed'];
export const isTerminal = (s: JobStatus | undefined): boolean => !!s && TERMINAL_STATUSES.includes(s);

/**
 * Poll a job until it reaches a terminal state.
 *
 * - Stops when the job is succeeded/failed (TanStack `enabled` flips off).
 * - Stops on unmount (react-query cleans up the interval).
 * - `refetchInterval` is only active while non-terminal, so no overlapping
 *   requests and no infinite polling after completion.
 * - Retries transient network blips only while non-terminal.
 */
export function useJobPolling(jobId: string | null | undefined, intervalMs = 1500) {
  const enabled = !!jobId;
  const query = useQuery({
    queryKey: ['job', jobId],
    queryFn: ({ signal }) => jobsApi.get(jobId as string, signal),
    enabled,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return isTerminal(status) ? false : intervalMs;
    },
    refetchIntervalInBackground: false,
    retry: (failureCount, error) => {
      // Don't retry hard 4xx (auth, not-found) — only transient/5xx.
      const status = (error as { status?: number })?.status;
      if (status && status >= 400 && status < 500) return false;
      return failureCount < 3;
    },
  });
  return query as ReturnType<typeof useQuery<JobInfo>>;
}
