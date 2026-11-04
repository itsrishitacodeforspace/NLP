'use client';

import * as React from 'react';
import { useParams } from 'next/navigation';
import { Hourglass } from 'lucide-react';
import { Disclaimer } from '@/components/layout/disclaimer';
import { ClauseDocument } from '@/components/review/clause-document';
import { FindingDetail } from '@/components/review/finding-detail';
import { ErrorState } from '@/components/ui/state';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { isApiError } from '@/lib/api/errors';
import {
  useContractSummary,
  useClauses,
  useRisks,
} from '@/features/analysis/use-analysis';
import type { Clause, ContractSummary, RiskFlag } from '@/types';

export interface ReviewData {
  summary: ContractSummary;
  clauses: Clause[];
  risks: RiskFlag[];
}

/**
 * Client-side review workspace. Fetches via react-query hooks (works with
 * backend auth on or off). When `data` is provided the page already has the
 * contract, clauses, and risks (e.g. a future server fetch); until the hooks
 * resolve the workspace renders from `data` instead of the skeleton.
 */
export function ReviewWorkspace({ data }: { contractId: string; data: ReviewData | null }) {
  const params = useParams<{ contractId: string }>();
  const contractId = params?.contractId;

  const summaryQuery = useContractSummary(contractId);
  const clausesQuery = useClauses(contractId);
  const risksQuery = useRisks(contractId);



  const [searchInput, setSearchInput] = React.useState('');
  const [selectedRiskId, setSelectedRiskId] = React.useState<string | null>(null);

  const clauseEls = React.useRef(new Map<string, HTMLElement>());
  const registerClauseEl = React.useCallback(
    (clauseId: string, el: HTMLElement | null) => {
      if (el) clauseEls.current.set(clauseId, el);
      else clauseEls.current.delete(clauseId);
    },
    []
  );

  const scrollToClause = React.useCallback((clauseId: string) => {
    const el = clauseEls.current.get(clauseId);
    el?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, []);

  // Memoised so the downstream useMemo hooks keep a stable reference; the
  // `?? []` fallback would otherwise allocate a new array on every render and
  // make their dependencies change each time (react-hooks/exhaustive-deps).
  const risks = React.useMemo(
    () => risksQuery.data?.risks ?? data?.risks ?? [],
    [risksQuery.data, data]
  );
  const selectedRisk = React.useMemo(
    () => risks.find((r) => r.risk_id === selectedRiskId) ?? null,
    [risks, selectedRiskId]
  );

  // Auto-scroll the document to the selected finding's clause.
  const lastScrolledRisk = React.useRef<string | null>(null);
  React.useEffect(() => {
    if (!selectedRiskId || lastScrolledRisk.current === selectedRiskId) return;
    lastScrolledRisk.current = selectedRiskId;
    const clauseId = selectedRisk?.clause_id ?? null;
    if (clauseId) scrollToClause(clauseId);
  }, [selectedRiskId, selectedRisk, scrollToClause]);

  // Loading only while no data is available: server data (when present) is
  // rendered immediately, so a background refetch never blanks the page.
  const loading =
    !summaryQuery.isError &&
    !clausesQuery.isError &&
    !risksQuery.isError &&
    (summaryQuery.isPending || clausesQuery.isPending || risksQuery.isPending) &&
    !summaryQuery.data &&
    !clausesQuery.data &&
    !risksQuery.data;

  // 404 / 409 from the summary endpoint.
  const is404 = isApiError(summaryQuery.error) && summaryQuery.error.isNotFound;
  const is409 = isApiError(summaryQuery.error) && summaryQuery.error.isConflict;

  const refetchAll = React.useCallback(() => {
    void summaryQuery.refetch();
    void clausesQuery.refetch();
    void risksQuery.refetch();
  }, [summaryQuery, clausesQuery, risksQuery]);

  if (loading) {
    return <PageSkeleton />;
  }

  if (is404) {
    return (
      <ErrorState
        title="Contract not found or no access"
        description="The contract may have been deleted, or your account does not have access to it."
        action={<Button variant="outline" onClick={refetchAll}>Try again</Button>}
        className="min-h-[60vh]"
      />
    );
  }

  if (is409) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="flex flex-col items-center gap-3 text-center">
          <Hourglass className="h-8 w-8 text-muted-foreground" aria-hidden />
          <h1 className="text-lg font-semibold">Still processing</h1>
          <p className="max-w-md text-sm text-muted-foreground">
            Analysis for this contract has not finished yet. Check back in a moment — the review
            workspace will appear once the job completes.
          </p>
          <Button variant="outline" onClick={refetchAll}>Refresh</Button>
        </div>
      </div>
    );
  }

  if (summaryQuery.error || clausesQuery.error || risksQuery.error) {
    const err = summaryQuery.error ?? clausesQuery.error ?? risksQuery.error;
    return (
      <ErrorState
        title="Failed to load contract review"
        description={err instanceof Error ? err.message : 'Unexpected error.'}
        action={<Button variant="outline" onClick={refetchAll}>Retry</Button>}
        className="min-h-[60vh]"
      />
    );
  }

  const summary = summaryQuery.data ?? data?.summary;
  const clauses = clausesQuery.data?.clauses ?? data?.clauses ?? [];
  if (!summary) {
    return <PageSkeleton />;
  }

  return (
    <div className="flex min-h-[calc(100vh-9rem)] flex-col gap-4">
      <div className="flex flex-col gap-4 lg:flex-row">
        <div className="min-h-0 flex-1">
          <ClauseDocument
            summary={summary}
            clauses={clauses}
            risks={risks}
            selectedRiskId={selectedRiskId}
            searchInput={searchInput}
            onSearchInputChange={setSearchInput}
            onSelectRisk={setSelectedRiskId}
            registerClauseEl={registerClauseEl}
          />
        </div>
        <div className="w-full shrink-0 lg:w-[400px]">
          <FindingDetail risk={selectedRisk} onGoToClause={scrollToClause} hasRisks={risks.length > 0} />
        </div>
      </div>
      <Disclaimer />
    </div>
  );
}

function PageSkeleton() {
  return (
    <div className="flex min-h-[60vh] flex-col gap-4 lg:flex-row">
      <div className="flex min-h-0 flex-1 flex-col gap-4">
        <div className="border border-border bg-card p-5">
          <Skeleton className="h-6 w-1/2" />
          <Skeleton className="mt-2 h-4 w-3/4" />
          <Skeleton className="mt-4 h-3 w-2/3" />
        </div>
        <div className="border border-border bg-card p-5">
          <Skeleton className="h-9 w-full" />
        </div>
        <div className="min-h-64 space-y-3 border border-border bg-card p-5">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="space-y-2">
              <Skeleton className="h-4 w-1/3" />
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-5/6" />
            </div>
          ))}
        </div>
      </div>
      <div className="w-full shrink-0 border border-border bg-card p-5 lg:w-[400px]">
        <Skeleton className="h-5 w-3/4" />
        <Skeleton className="mt-3 h-4 w-full" />
        <Skeleton className="mt-2 h-4 w-full" />
        <Skeleton className="mt-4 h-4 w-2/3" />
      </div>
    </div>
  );
}
