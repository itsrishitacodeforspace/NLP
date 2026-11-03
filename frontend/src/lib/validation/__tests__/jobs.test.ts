import { describe, expect, it } from 'vitest';
import { JobInfoSchema, parseJobInfo, tryParseJobInfo } from '@/lib/validation/jobs';

const VALID_JOB = {
  job_id: 'job-123',
  contract_id: 'c-abc',
  owner: 'anonymous',
  status: 'running' as const,
  progress: 0.1,
  message: 'Parsing document',
  created_at: '2026-11-03T12:00:00',
  finished_at: null,
  result: null,
  error: null,
  result_error: null,
};

describe('validation/jobs.ts — JobInfoSchema', () => {
  it('parses a valid running job', () => {
    expect(parseJobInfo(VALID_JOB)).toEqual(VALID_JOB);
  });

  it('parses a minimal payload (optional fields omitted)', () => {
    expect(tryParseJobInfo({ job_id: 'j', contract_id: 'c', owner: 'o', status: 'queued', progress: 0 })).toEqual({
      job_id: 'j',
      contract_id: 'c',
      owner: 'o',
      status: 'queued',
      progress: 0,
    });
  });

  it.each(['queued', 'running', 'succeeded', 'failed'] as const)('accepts status %s', (status) => {
    expect(JobInfoSchema.safeParse({ ...VALID_JOB, status }).success).toBe(true);
  });

  it('rejects an unknown status', () => {
    expect(JobInfoSchema.safeParse({ ...VALID_JOB, status: 'in-progress' }).success).toBe(false);
  });

  it('rejects progress outside 0..1', () => {
    expect(JobInfoSchema.safeParse({ ...VALID_JOB, progress: -0.1 }).success).toBe(false);
    expect(JobInfoSchema.safeParse({ ...VALID_JOB, progress: 1.5 }).success).toBe(false);
  });

  it('rejects a missing required field', () => {
    const { job_id: _omit, ...rest } = VALID_JOB;
    expect(JobInfoSchema.safeParse(rest).success).toBe(false);
  });

  it('rejects a non-object payload', () => {
    expect(tryParseJobInfo(null)).toBeNull();
    expect(tryParseJobInfo('job-123')).toBeNull();
    expect(tryParseJobInfo(42)).toBeNull();
  });

  it('parseJobInfo throws ZodError on bad data, tryParseJobInfo returns null', () => {
    expect(() => parseJobInfo({ ...VALID_JOB, status: 'nope' })).toThrowError(/status/);
    expect(tryParseJobInfo({ ...VALID_JOB, status: 'nope' })).toBeNull();
  });
});
