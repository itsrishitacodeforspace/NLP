import { format, parseISO } from 'date-fns';
import type { JobStatus } from '@/types';

/** Format an ISO datetime from the backend (naive UTC) for display. */
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    // Backend sends naive UTC; tag it so we render a stable local time.
    const d = iso.endsWith('Z') || iso.includes('+') ? parseISO(iso) : parseISO(iso + 'Z');
    return format(d, 'dd MMM yyyy, HH:mm');
  } catch {
    return iso;
  }
}

export function formatRelative(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    const d = new Date(iso.endsWith('Z') ? iso : iso + 'Z');
    const diff = Date.now() - d.getTime();
    const min = Math.round(diff / 60000);
    if (min < 1) return 'just now';
    if (min < 60) return `${min}m ago`;
    const hr = Math.round(min / 60);
    if (hr < 24) return `${hr}h ago`;
    return format(d, 'dd MMM');
  } catch {
    return iso;
  }
}

export const JOB_STATUS_LABEL: Record<JobStatus, string> = {
  queued: 'Queued',
  running: 'Running',
  succeeded: 'Completed',
  failed: 'Failed',
};

/** Map a job message to a truthful pipeline stage label (no invented %). */
export function jobStageLabel(status: JobStatus, message?: string | null): string {
  switch (status) {
    case 'queued':
      return 'Waiting to start';
    case 'running':
      return (message && !message.includes('Parsing') ? message : 'Analyzing document');
    case 'succeeded':
      return 'Analysis complete';
    case 'failed':
      return 'Analysis failed';
  }
}
