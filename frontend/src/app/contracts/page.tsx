'use client';

import Link from 'next/link';
import { PageTitle } from '@/components/editorial';
import { SeverityBadge } from '@/components/risks/badges';
import { Button } from '@/components/ui/button';
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/state';
import { useRecentContracts } from '@/features/analysis/use-analysis';
import { formatRelative } from '@/lib/format';
import type { JobInfo } from '@/types';

export default function ContractsPage() {
  const { data, isLoading, isError, refetch } = useRecentContracts();
  const jobs = (data?.jobs ?? []).filter((j: JobInfo) => j.result != null);

  return (
    <div className="space-y-6">
      <PageTitle
        kicker="Register"
        title="Contracts"
        meta="Every completed analysis, indexed. Select a row to open its review."
      >
        <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
          {String(jobs.length).padStart(2, '0')} analysed
        </span>
      </PageTitle>

      {isLoading ? <LoadingState label="Loading contracts…" className="py-10 justify-center" /> : null}

      {isError ? (
        <ErrorState
          title="Failed to load contracts"
          description="The list of analyses could not be fetched."
          action={<Button variant="outline" onClick={() => refetch()}>Retry</Button>}
          className="border-x-0"
        />
      ) : null}

      {!isLoading && !isError && jobs.length === 0 ? (
        <EmptyState
          title="No contracts analysed yet"
          description="Upload a contract to start building your register."
          className="border-x-0"
        />
      ) : null}

      {!isLoading && !isError && jobs.length > 0 ? (
        <div className="overflow-x-auto border-y border-border">
          <table className="w-full min-w-[640px] text-sm">
            <thead>
              <tr className="border-b border-border text-left font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                <th className="w-10 py-2.5 pr-3 font-normal">№</th>
                <th className="py-2.5 pr-3 font-normal">Contract</th>
                <th className="py-2.5 pr-3 font-normal">Type</th>
                <th className="py-2.5 pr-3 font-normal">Risk</th>
                <th className="py-2.5 pr-3 text-right font-normal">Clauses</th>
                <th className="py-2.5 font-normal">Analysed</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {jobs.map((job, i) => {
                const contract = job.result?.contract;
                return (
                  <tr key={job.job_id} className="transition-colors hover:bg-accent/50">
                    <td className="py-3 pr-3 font-mono text-[11px] tabular-nums text-muted-foreground">
                      {String(i + 1).padStart(2, '0')}
                    </td>
                    <td className="py-3 pr-3">
                      <Link
                        href={`/contracts/${job.contract_id}/review`}
                        className="font-medium text-foreground hover:text-primary"
                      >
                        {contract?.title ?? job.contract_id}
                      </Link>
                      {contract?.parties?.length ? (
                        <span className="mt-0.5 block truncate text-xs text-muted-foreground">
                          {contract.parties.join(' · ')}
                        </span>
                      ) : null}
                    </td>
                    <td className="py-3 pr-3 font-mono text-xs text-muted-foreground">
                      {contract?.contract_type ?? '—'}
                    </td>
                    <td className="py-3 pr-3">
                      {contract ? <SeverityBadge severity={contract.overall_risk_level} /> : null}
                    </td>
                    <td className="py-3 pr-3 text-right font-mono text-xs tabular-nums text-muted-foreground">
                      {contract?.clause_count ?? '—'}
                    </td>
                    <td className="py-3 font-mono text-xs text-muted-foreground">
                      {formatRelative(job.finished_at ?? job.created_at)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
