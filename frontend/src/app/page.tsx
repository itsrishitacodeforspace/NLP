'use client';

import Link from 'next/link';
import * as React from 'react';

import { DropZone } from '@/components/contracts/drop-zone';
import { Disclaimer } from '@/components/layout/disclaimer';
import { SeverityBadge } from '@/components/risks/badges';
import { SectionHeading } from '@/components/editorial';
import { EmptyState, LoadingState } from '@/components/ui/state';
import { useRecentContracts } from '@/features/analysis/use-analysis';
import { formatRelative } from '@/lib/format';
import type { JobInfo } from '@/types';

/* Real checks the rule engine runs — surfaced honestly, not invented stats. */
const CHECKS = [
  ['Stamp duty', 'Indian Stamp Act 1899 · ss. 33, 35'],
  ['Arbitration seat', 'BALCO · BGS SGS Soma (seat ≠ venue)'],
  ['Indemnity gap', 'Contract Act §124–125'],
  ['TDS / GST signals', 'withholding & supply compliance'],
  ['Hidden obligations', 'deadlines, notice periods, auto-renewal'],
] as const;

const HOW_IT_WORKS = [
  { title: 'Upload', text: 'Drop a PDF, DOCX, TXT or Markdown agreement and pick your side of the deal.' },
  { title: 'Analyse', text: 'It is parsed, segmented and run through explainable Indian-statutory risk rules.' },
  { title: 'Review', text: 'Read the flagged clauses in context, each with its evidence and legal pointer.' },
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
        title="No completed analyses yet"
        description="Upload a contract above and it will appear here once analysis finishes."
        className="border-x-0"
      />
    );
  }

  return (
    <ul className="divide-y divide-border border-y border-border">
      {completed.map((job, i) => {
        const contract = job.result?.contract;
        return (
          <li key={job.job_id}>
            <Link
              href={`/contracts/${job.contract_id}/review`}
              className="flex items-baseline gap-3 px-1 py-3 transition-colors hover:bg-accent/60 sm:gap-4"
            >
              <span aria-hidden className="w-6 shrink-0 font-mono text-[11px] tabular-nums text-muted-foreground">
                {String(i + 1).padStart(2, '0')}
              </span>
              <span className="min-w-0 flex-1 truncate text-sm font-medium">
                {contract?.title ?? job.contract_id}
              </span>
              {contract ? <SeverityBadge severity={contract.overall_risk_level} className="shrink-0" /> : null}
              <span className="hidden shrink-0 font-mono text-[11px] text-muted-foreground sm:inline">
                {formatRelative(job.finished_at ?? job.created_at)}
              </span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

export default function HomePage() {
  return (
    <div className="space-y-11">
      {/* Hero — asymmetric, serif-led, no gradient. */}
      <header className="grid gap-8 pb-9 lg:grid-cols-[1.4fr_1fr] lg:items-end lg:gap-12">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-primary">
            § Contract intelligence
          </p>
          <h1 className="mt-3.5 font-display text-[2.6rem] font-semibold leading-[0.98] tracking-tight sm:text-6xl">
            Read the redline
            <br />
            before you sign.
          </h1>
          <p className="mt-5 max-w-xl text-base leading-relaxed text-muted-foreground">
            BharatContract reads Indian and cross-border agreements the way counsel would — flagging
            dangerous clauses, missing stamp duties, arbitration traps and hidden obligations, each with
            the statutory or case-law pointer behind it.
          </p>
        </div>

        <aside className="border border-border bg-card">
          <p className="border-b border-border px-4 py-2.5 font-mono text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
            What it checks
          </p>
          <ul className="divide-y divide-border">
            {CHECKS.map(([name, detail]) => (
              <li key={name} className="flex flex-col gap-0.5 px-4 py-2.5">
                <span className="font-mono text-[12px] text-foreground">{name}</span>
                <span className="text-xs leading-relaxed text-muted-foreground">{detail}</span>
              </li>
            ))}
          </ul>
        </aside>
      </header>

      {/* Upload */}
      <section className="space-y-4">
        <SectionHeading index="01" title="Analyse a contract" />
        <DropZone />
      </section>

      {/* Recent — a numbered index, not a card grid. */}
      <section className="space-y-4">
        <SectionHeading
          index="02"
          title="Recent contracts"
          action={<span className="font-mono text-[11px] text-muted-foreground">indexed</span>}
        />
        <RecentContracts />
      </section>

      {/* How it works — a divided editorial strip, no icon cards. */}
      <section className="space-y-4">
        <SectionHeading index="03" title="How it works" />
        <ol className="grid divide-y divide-border border-y border-border sm:grid-cols-3 sm:divide-x sm:divide-y-0">
          {HOW_IT_WORKS.map((step, i) => (
            <li key={step.title} className="px-1 py-4 sm:px-5 sm:first:pl-0 sm:last:pr-0">
              <span className="font-mono text-[11px] tracking-widest text-primary">0{i + 1}</span>
              <h3 className="mt-1.5 font-display text-base font-semibold tracking-tight">{step.title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{step.text}</p>
            </li>
          ))}
        </ol>
        <p className="text-xs text-muted-foreground">
          There is no separate demo endpoint — the upload form analyses any real contract you provide.{' '}
          <Link href="/upload" className="underline underline-offset-4 hover:text-primary">
            Go to upload
          </Link>
        </p>
      </section>

      <Disclaimer />
    </div>
  );
}
