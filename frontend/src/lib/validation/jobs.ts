/**
 * Runtime validation for the JobInfo shape returned by GET /api/v1/jobs/{id}.
 *
 * NOTE (additive only): this does NOT rewire the API layer — it exists so
 * callers that poll a job can reject malformed payloads early instead of
 * crashing on `job.status`.
 */
import { z } from 'zod';

export const JobStatusSchema = z.enum(['queued', 'running', 'succeeded', 'failed']);

export const JobInfoSchema = z.object({
  job_id: z.string(),
  contract_id: z.string(),
  owner: z.string(),
  status: JobStatusSchema,
  progress: z.number().min(0).max(1),
  message: z.string().nullable().optional(),
  created_at: z.string().optional(),
  finished_at: z.string().nullable().optional(),
  result: z.unknown().nullable().optional(),
  error: z.string().nullable().optional(),
  result_error: z.string().nullable().optional(),
});

export type ValidJobInfo = z.infer<typeof JobInfoSchema>;

/** Parse an unknown payload as JobInfo. Throws ZodError when invalid. */
export function parseJobInfo(data: unknown): ValidJobInfo {
  return JobInfoSchema.parse(data);
}

/** Safe variant: returns null instead of throwing. */
export function tryParseJobInfo(data: unknown): ValidJobInfo | null {
  const r = JobInfoSchema.safeParse(data);
  return r.success ? r.data : null;
}
