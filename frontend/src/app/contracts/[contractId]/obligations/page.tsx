'use client';

import * as React from 'react';
import { useParams } from 'next/navigation';
import { LayoutGrid, List } from 'lucide-react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/state';
import { Disclaimer } from '@/components/layout/disclaimer';
import { ObligationsTable } from '@/components/obligations/obligations-table';
import { ObligationsTimeline } from '@/components/obligations/obligations-timeline';
import { useContractSummary, useObligations } from '@/features/analysis/use-analysis';
import { cn } from '@/lib/utils';

type View = 'table' | 'timeline';

export default function ObligationsPage() {
  const params = useParams<{ contractId: string }>();
  const contractId = params?.contractId as string | undefined;
  const summaryQ = useContractSummary(contractId);
  const obligationsQ = useObligations(contractId);
  const [view, setView] = React.useState<View>('table');

  if (!contractId) {
    return <ErrorState title="Missing contract ID" description="No contract ID in the URL." />;
  }
  if (obligationsQ.isPending) {
    return <LoadingState label="Loading obligations…" className="p-10" />;
  }
  if (obligationsQ.isError) {
    const err = obligationsQ.error as { message?: string } | null;
    return (
      <div className="space-y-4 p-6">
        <ErrorState
          title="Could not load obligations"
          description={err?.message ?? 'The contract may not exist or analysis is incomplete.'}
        />
        <Disclaimer />
      </div>
    );
  }

  const summary = summaryQ.data;
  const obligations = obligationsQ.data.obligations;

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Obligation tracker</h1>
        <p className="text-sm text-muted-foreground">
          {summary?.title ?? contractId}
          {summary?.parties && summary.parties.length > 0 ? (
            <> · {summary.parties.join(' · ')}</>
          ) : null}
          {typeof summary?.obligation_count === 'number' ? (
            <span className="text-muted-foreground"> · {obligations.length} obligations</span>
          ) : null}
        </p>
      </header>

      {/* View toggle */}
      <div className="inline-flex rounded-lg border p-0.5">
        {(
          [
            { id: 'table', label: 'Table', icon: LayoutGrid },
            { id: 'timeline', label: 'Timeline', icon: List },
          ] as const
        ).map(({ id, label, icon: Icon }) => (
          <Button
            key={id}
            variant={view === id ? 'secondary' : 'ghost'}
            size="sm"
            onClick={() => setView(id)}
            className="gap-1.5"
            aria-pressed={view === id}
          >
            <Icon className="h-3.5 w-3.5" aria-hidden />
            {label}
          </Button>
        ))}
      </div>

      {obligations.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Obligations</CardTitle>
            <CardDescription>
              Duties, rights, prohibitions and conditions extracted from the contract.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <EmptyState
              icon={<List className="h-6 w-6" aria-hidden />}
              title="No obligations extracted"
              description="The analyzer did not identify any obligations, rights, prohibitions or conditions in this contract."
            />
          </CardContent>
        </Card>
      ) : view === 'table' ? (
        <ObligationsTable obligations={obligations} contractId={contractId} />
      ) : (
        <ObligationsTimeline obligations={obligations} />
      )}

      <p className="text-xs text-muted-foreground">
        Statuses are derived only from definite, machine-parsed deadline dates. An
        expression such as “30 days” is displayed but never treated as a calendar date.
      </p>

      <Disclaimer />
    </div>
  );
}
