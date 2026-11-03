'use client';

import Link from 'next/link';
import * as React from 'react';
import { ArrowRight, FileText, ListChecks, Search, UploadCloud } from 'lucide-react';

import { DropZone } from '@/components/contracts/drop-zone';
import { Disclaimer } from '@/components/layout/disclaimer';
import { SeverityBadge } from '@/components/risks/badges';
import { Card } from '@/components/ui/card';
import { EmptyState, LoadingState } from '@/components/ui/state';
import { useRecentContracts } from '@/features/analysis/use-analysis';
import { formatRelative } from '@/lib/format';
import type { JobInfo } from '@/types';

const HOW_IT_WORKS = [
  {
    icon: UploadCloud,
    title: 'Upload',
    text: 'Drop in a PDF, DOCX, TXT or Markdown contract and pick your side of the deal.',
  },
  {
    icon: Search,
    title: 'Analyze',
    text: 'We parse and segment the document, extract obligations and run explainable risk rules (Indian statutory context included).',
  },
  {
    icon: ListChecks,
    title: 'Review',
    text: 'Browse flagged clauses and obligations with the evidence behind each finding.',
  },
] as const;

function RecentContracts() {
  const { data, isLoading, isError } = useRecentContracts();
  const completed = React.useMemo(
    () => (data?.jobs ?? []).filter((j: JobInfo) => j.result !== null && j.result !== undefined),
    [data]
  );

  if (isLoading) return <LoadingState label="Loading recent contracts…" className="py-8 justify-center" />;
  if (isError) return null;
  if (completed.length === 0) {
    return (
      <EmptyState
        icon={<FileText className="h-6 w-6" aria-hidden />}
        title="No completed analyses yet"
        description="Upload a contract above and it will appear here once analysis finishes."
      />
    );
  }

  return (
    <ul className="grid gap-3 sm:grid-cols-2">
      {completed.map((job) => {
        const contract = job.result?.contract;
        return (
          <li key={job.job_id}>
            <Link
              href={`/contracts/${job.contract_id}/review`}
              className="block rounded-lg border bg-card p-4 transition-colors hover:bg-accent"
            >
              <div className="flex items-start justify-between gap-3">
                <span className="line-clamp-2 text-sm font-medium">{contract?.title ?? job.contract_id}</span>
                {contract ? <SeverityBadge severity={contract.overall_risk_level} className="shrink-0" /> : null}
              </div>
              <p className="mt-1 text-xs text-muted-foreground">{formatRelative(job.finished_at ?? job.created_at)}</p>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

export default function HomePage() {
  return (
    <div className="space-y-8">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">BharatContract AI</h1>
        <p className="text-sm text-muted-foreground">
          Indian-context contract intelligence: risk-aware clause extraction and obligation tracking.
        </p>
      </header>

      <DropZone />

      <section className="space-y-3">
        <h2 className="text-lg font-semibold tracking-tight">Recent contracts</h2>
        <RecentContracts />
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold tracking-tight">How it works</h2>
        <div className="grid gap-3 sm:grid-cols-3">
          {HOW_IT_WORKS.map((step, i) => {
            const Icon = step.icon;
            return (
              <Card key={step.title} className="p-4">
                <div className="flex items-center gap-2">
                  <Icon className="h-4 w-4 text-muted-foreground" aria-hidden />
                  <span className="text-sm font-medium">
                    {i + 1}. {step.title}
                  </span>
                </div>
                <p className="mt-2 text-sm text-muted-foreground">{step.text}</p>
              </Card>
            );
          })}
        </div>
        <p className="text-xs text-muted-foreground">
          There is no separate demo endpoint — the upload form above analyzes any real contract you provide.{' '}
          <Link href="/upload" className="underline underline-offset-4">
            Go to upload
          </Link>{' '}
          <ArrowRight className="inline h-3 w-3" aria-hidden />
        </p>
      </section>

      <Disclaimer />
    </div>
  );
}
