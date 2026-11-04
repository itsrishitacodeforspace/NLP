'use client';

import Link from 'next/link';
import * as React from 'react';
import { PageTitle } from '@/components/editorial';
import { SeverityBadge } from '@/components/risks/badges';
import { Button } from '@/components/ui/button';
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/state';
import { useRecentContracts } from '@/features/analysis/use-analysis';
import type { JobInfo, Obligation } from '@/types';

interface GlobalObligation {
  key: string;
  contractId: string;
  contractTitle: string;
  obligation: Obligation;
}

const TYPE_LABEL: Record<string, string> = {
  obligation: 'Obligation',
  right: 'Right',
  prohibition: 'Prohibition',
  condition: 'Condition',
};

export default function ObligationsPage() {
  const { data, isLoading, isError, refetch } = useRecentContracts();

  const rows = React.useMemo<GlobalObligation[]>(() => {
    const out: GlobalObligation[] = [];
    for (const job of (data?.jobs ?? []) as JobInfo[]) {
      const result = job.result;
      if (!result?.obligations?.length) continue;
      const title = result.contract?.title ?? job.contract_id;
      for (const o of result.obligations) {
        out.push({
          key: `${job.contract_id}:${o.obligation_id}`,
          contractId: job.contract_id,
          contractTitle: title,
          obligation: o,
        });
      }
    }
    // Deadline-bearing first, then by risk.
    const riskRank: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };
    out.sort(
      (a, b) =>
        Number(b.obligation.deadline_date != null) - Number(a.obligation.deadline_date != null) ||
        (riskRank[a.obligation.risk_level] ?? 4) - (riskRank[b.obligation.risk_level] ?? 4)
    );
    return out;
  }, [data]);

  return (
    <div className="space-y-6">
      <PageTitle
        kicker="Register"
        title="Obligations"
        meta="Deadlines, notice periods and duties extracted across your analysed contracts, deadline-bearing first."
      >
        <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
          {String(rows.length).padStart(3, '0')} found
        </span>
      </PageTitle>

      {isLoading ? <LoadingState label="Loading obligations…" className="py-10 justify-center" /> : null}

      {isError ? (
        <ErrorState
          title="Failed to load obligations"
          description="The obligation register could not be fetched."
          action={<Button variant="outline" onClick={() => refetch()}>Retry</Button>}
          className="border-x-0"
        />
      ) : null}

      {!isLoading && !isError && rows.length === 0 ? (
        <EmptyState
          title="No obligations extracted yet"
          description="Analyse a contract and its obligations will be collected here."
          className="border-x-0"
        />
      ) : null}

      {!isLoading && !isError && rows.length > 0 ? (
        <div className="overflow-x-auto border-y border-border">
          <table className="w-full min-w-[720px] text-sm">
            <thead>
              <tr className="border-b border-border text-left font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                <th className="w-10 py-2.5 pr-3 font-normal">№</th>
                <th className="py-2.5 pr-3 font-normal">Type</th>
                <th className="py-2.5 pr-3 font-normal">Obligation</th>
                <th className="py-2.5 pr-3 font-normal">Deadline</th>
                <th className="py-2.5 pr-3 font-normal">Risk</th>
                <th className="py-2.5 font-normal">Contract</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {rows.map((row, i) => {
                const o = row.obligation;
                const summary = [o.subject, o.action, o.object].filter(Boolean).join(' ') || o.text;
                return (
                  <tr key={row.key} className="align-top transition-colors hover:bg-accent/50">
                    <td className="py-3 pr-3 font-mono text-[11px] tabular-nums text-muted-foreground">
                      {String(i + 1).padStart(2, '0')}
                    </td>
                    <td className="py-3 pr-3">
                      <span className="border border-border px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-[0.06em] text-muted-foreground">
                        {TYPE_LABEL[o.obligation_type] ?? o.obligation_type}
                      </span>
                    </td>
                    <td className="max-w-[38ch] py-3 pr-3">
                      <span className="line-clamp-2 leading-relaxed">{summary}</span>
                    </td>
                    <td className="py-3 pr-3 font-mono text-xs">
                      {o.deadline_date ?? o.deadline_expression ?? (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </td>
                    <td className="py-3 pr-3">
                      <SeverityBadge severity={o.risk_level} />
                    </td>
                    <td className="py-3 text-xs">
                      <Link
                        href={`/contracts/${row.contractId}/obligations`}
                        className="text-muted-foreground hover:text-primary"
                      >
                        {row.contractTitle}
                      </Link>
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
