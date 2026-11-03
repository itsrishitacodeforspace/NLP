'use client';

import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import * as React from 'react';
import { CheckCircle2, Loader2 } from 'lucide-react';

import { Disclaimer } from '@/components/layout/disclaimer';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import { ErrorState, LoadingState } from '@/components/ui/state';
import { useJobPolling } from '@/features/jobs/use-jobs';
import { jobStageLabel } from '@/lib/format';
import { cn } from '@/lib/utils';
import type { JobInfo } from '@/types';

const STAGES = ['Queued', 'Parsing', 'Analyzing', 'Persisting', 'Done'] as const;
type Stage = (typeof STAGES)[number];

/** Map the real backend (status, message) pair onto a pipeline stage. No interpolation. */
function currentStage(job: JobInfo): Stage {
  if (job.status === 'succeeded') return 'Done';
  const msg = (job.message ?? '').toLowerCase();
  if (job.status === 'queued') return 'Queued';
  if (msg.includes('persist') || msg.includes('saving') || job.progress >= 0.7) return 'Persisting';
  if (msg.includes('pars')) return 'Parsing';
  return 'Analyzing';
}

export default function JobPage() {
  const params = useParams<{ jobId: string }>();
  const router = useRouter();
  const jobId = params.jobId;
  const { data: job, isLoading, isError, error } = useJobPolling(jobId);

  // On success: short pause so the "Done" state is visible, then hand off to the review page.
  React.useEffect(() => {
    if (job?.status === 'succeeded') {
      const t = window.setTimeout(() => router.replace(`/contracts/${job.contract_id}/review`), 800);
      return () => window.clearTimeout(t);
    }
  }, [job, router]);

  if (isLoading || !job) {
    return (
      <div className="mx-auto max-w-2xl space-y-6">
        <h1 className="text-xl font-semibold tracking-tight">Analysis in progress</h1>
        <Card>
          <CardContent className="space-y-4 p-6">
            <LoadingState label="Fetching job status…" />
            <Progress value={0} label="Loading" className="h-1.5 opacity-40" />
            <Skeleton className="h-10 w-2/3" />
          </CardContent>
        </Card>
        {isError ? (
          <ErrorState
            title="Could not load this job"
            description={error instanceof Error ? error.message : 'Unknown error'}
            action={
              <Link href="/">
                <Button variant="outline">Back to home</Button>
              </Link>
            }
          />
        ) : null}
        <Disclaimer />
      </div>
    );
  }

  if (job.status === 'failed') {
    return (
      <div className="mx-auto max-w-2xl space-y-6">
        <h1 className="text-xl font-semibold tracking-tight">Analysis failed</h1>
        <ErrorState
          title="Analysis failed"
          description={job.error ?? 'The backend reported a failure without details. The document may be unreadable or unsupported.'}
          action={
            <div className="flex gap-2">
              <Link href="/upload">
                <Button variant="outline">Try another file</Button>
              </Link>
              <Link href="/">
                <Button>Back to home</Button>
              </Link>
            </div>
          }
        />
        <Disclaimer />
      </div>
    );
  }

  const stage = currentStage(job);
  const stageIndex = STAGES.indexOf(stage);
  const succeeded = job.status === 'succeeded';

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="text-xl font-semibold tracking-tight">Analyzing your contract</h1>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            {succeeded ? (
              <CheckCircle2 className="h-4 w-4 text-risk-low" aria-hidden />
            ) : (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            )}
            {jobStageLabel(job.status, job.message)}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <div>
            <div className="mb-2 flex items-baseline justify-between text-xs text-muted-foreground">
              <span>Reported progress (no interpolation)</span>
              <span>{Math.round(job.progress * 100)}%</span>
            </div>
            <Progress value={job.progress} label={jobStageLabel(job.status, job.message)} />
          </div>

          <ol className="flex items-start gap-1" aria-label="Pipeline stages">
            {STAGES.map((s, i) => {
              const done = succeeded || i < stageIndex;
              const active = !succeeded && i === stageIndex;
              return (
                <li key={s} className="flex flex-1 flex-col items-center gap-1.5">
                  <div
                    className={cn(
                      'h-2 w-full rounded-full',
                      done ? 'bg-primary' : active ? 'bg-primary/50' : 'bg-muted'
                    )}
                    aria-hidden
                  />
                  <span
                    className={cn(
                      'text-[11px]',
                      done ? 'font-medium text-foreground' : active ? 'font-medium text-foreground' : 'text-muted-foreground'
                    )}
                  >
                    {s}
                  </span>
                </li>
              );
            })}
          </ol>

          <div className="space-y-2">
            {succeeded ? (
              <Button onClick={() => router.push(`/contracts/${job.contract_id}/review`)}>
                View analysis
              </Button>
            ) : (
              <p className="text-sm text-muted-foreground">
                {job.status === 'queued'
                  ? 'Your job is in the queue. This page updates automatically — keep it open.'
                  : `Working: ${job.message ?? 'analyzing'}. This page updates automatically.`}
              </p>
            )}
          </div>
        </CardContent>
      </Card>

      <Disclaimer />
    </div>
  );
}
