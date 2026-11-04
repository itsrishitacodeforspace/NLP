import { afterEach, describe, expect, it, vi } from 'vitest';
import { JOB_STATUS_LABEL, formatDateTime, formatRelative, jobStageLabel } from '@/lib/format';

// Pin "now" so relative buckets are deterministic.
const NOW = new Date('2026-11-03T12:00:00Z').getTime();

afterEach(() => {
  vi.useRealTimers();
});

describe('format.ts', () => {
  describe('formatDateTime', () => {
    it('treats naive-UTC ISO (no Z, no offset) as UTC', () => {
      // Rendering is in the viewer's timezone, so assert the parsed instant
      // (a naive stamp must equal its explicit-Z form) rather than a fixed
      // local hour, which would only hold in a UTC environment.
      const naive = formatDateTime('2026-11-03T12:00:00');
      expect(naive).toBe(formatDateTime('2026-11-03T12:00:00Z'));
      expect(naive).toContain('Nov');
      expect(naive).toContain('2026');
    });

    it('also accepts explicit Z and offset suffixes', () => {
      expect(formatDateTime('2026-11-03T12:00:00Z')).toBe(formatDateTime('2026-11-03T12:00:00'));
      expect(formatDateTime('2026-11-03T18:00:00+06:00')).toBe(formatDateTime('2026-11-03T12:00:00Z'));
    });

    it('returns an em-dash for empty input', () => {
      expect(formatDateTime(null)).toBe('—');
      expect(formatDateTime(undefined)).toBe('—');
      expect(formatDateTime('')).toBe('—');
    });

    it('returns the raw string when it cannot be parsed', () => {
      expect(formatDateTime('not-a-date')).toBe('not-a-date');
    });
  });

  describe('formatRelative', () => {
    it('renders "just now" for the current moment', () => {
      vi.setSystemTime(NOW);
      expect(formatRelative(new Date(NOW).toISOString().replace('Z', ''))).toBe('just now');
    });

    it('renders minute buckets', () => {
      vi.setSystemTime(NOW);
      const iso = new Date(NOW - 5 * 60_000).toISOString().replace('Z', '');
      expect(formatRelative(iso)).toBe('5m ago');
    });

    it('renders hour buckets', () => {
      vi.setSystemTime(NOW);
      const iso = new Date(NOW - 3 * 3_600_000).toISOString().replace('Z', '');
      expect(formatRelative(iso)).toBe('3h ago');
    });

    it('renders a short date beyond 24h (locale-stable assertion)', () => {
      vi.setSystemTime(NOW);
      const iso = new Date(NOW - 3 * 86_400_000).toISOString().replace('Z', '');
      // NOW is 2026-11-03T12:00Z, three days earlier is 2026-10-31T12:00Z.
      const out = formatRelative(iso);
      expect(out).toBe('31 Oct');
      expect(out).not.toMatch(/ago/);
    });

    it('handles empty and unparseable input', () => {
      expect(formatRelative(null)).toBe('—');
      expect(formatRelative(undefined)).toBe('—');
      expect(formatRelative('garbage')).toBe('garbage');
    });
  });

  describe('JOB_STATUS_LABEL', () => {
    it('labels every job status', () => {
      expect(JOB_STATUS_LABEL).toEqual({
        queued: 'Queued',
        running: 'Running',
        succeeded: 'Completed',
        failed: 'Failed',
      });
    });
  });

  describe('jobStageLabel', () => {
    it('queued → waiting', () => {
      expect(jobStageLabel('queued')).toBe('Waiting to start');
    });

    it('running → truthful message or generic analyzing label', () => {
      expect(jobStageLabel('running', 'Parsing document')).toBe('Analyzing document');
      expect(jobStageLabel('running', 'Persisting to graph')).toBe('Persisting to graph');
      expect(jobStageLabel('running')).toBe('Analyzing document');
      expect(jobStageLabel('running', null)).toBe('Analyzing document');
    });

    it('terminal states', () => {
      expect(jobStageLabel('succeeded')).toBe('Analysis complete');
      expect(jobStageLabel('failed')).toBe('Analysis failed');
    });
  });
});
