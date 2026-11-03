'use client';

import * as React from 'react';
import { FileSearch, GitBranch, RefreshCw } from 'lucide-react';

import { Disclaimer } from '@/components/layout/disclaimer';
import { GraphCanvas } from '@/components/graph/graph-canvas';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Separator } from '@/components/ui/separator';
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/state';
import { useGraph, useRecentContracts } from '@/features/analysis/use-analysis';
import { isApiError } from '@/lib/api/errors';
import type { JobInfo } from '@/types';

export default function GraphExplorerPage() {
  const { data, isLoading: loadingContracts } = useRecentContracts();
  const completed = React.useMemo(
    () => (data?.jobs ?? []).filter((j: JobInfo) => j.result !== null && j.result !== undefined),
    [data]
  );
  // De-duplicate: one entry per contract_id (newest job wins; jobs arrive newest-first).
  const contracts = React.useMemo(() => {
    const seen = new Set<string>();
    const out: { id: string; title: string }[] = [];
    for (const job of completed) {
      if (seen.has(job.contract_id)) continue;
      seen.add(job.contract_id);
      out.push({ id: job.contract_id, title: job.result?.contract?.title ?? job.contract_id });
    }
    return out;
  }, [completed]);

  const [selected, setSelected] = React.useState<string>('');
  const [manual, setManual] = React.useState('');

  // Default to the first available contract once the list loads.
  React.useEffect(() => {
    if (!selected && contracts.length > 0) setSelected(contracts[0].id);
  }, [contracts, selected]);

  const graph = useGraph(selected || null);
  const graphError = graph.error ?? null;
  const isNotFound = isApiError(graphError) && graphError.isNotFound;

  const retry = () => graph.refetch();
  const loadManual = () => {
    const id = manual.trim();
    if (id) setSelected(id);
  };

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
          <GitBranch className="h-5 w-5 text-muted-foreground" aria-hidden /> Graph Explorer
        </h1>
        <p className="text-sm text-muted-foreground">
          Contract → clause → obligation / risk relationships as returned by the backend. Only backend-produced
          edges are shown; nothing is inferred.
        </p>
      </header>

      <Card>
        <CardContent className="pt-5">
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex min-w-[260px] flex-1 flex-col gap-1.5 sm:max-w-md">
              <span className="text-xs font-medium text-muted-foreground">Contract</span>
              <select
                value={selected}
                onChange={(e) => setSelected(e.target.value)}
                disabled={loadingContracts}
                className="h-9 rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
              >
                {loadingContracts ? (
                  <option value="">Loading…</option>
                ) : contracts.length === 0 ? (
                  <option value="">No completed contracts yet</option>
                ) : (
                  contracts.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.title} — {c.id}
                    </option>
                  ))
                )}
              </select>
            </label>
            <form
              className="flex items-end gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                loadManual();
              }}
            >
              <label className="flex flex-col gap-1.5">
                <span className="text-xs font-medium text-muted-foreground">Or paste a contract_id</span>
                <Input
                  value={manual}
                  onChange={(e) => setManual(e.target.value)}
                  placeholder="c_2026…"
                  className="w-64"
                />
              </label>
              <Button type="submit" variant="outline" size="default">
                Load
              </Button>
            </form>
          </div>
        </CardContent>
      </Card>

      <Separator />

      <main>
        {graph.isLoading ? (
          <GraphCanvas skeletonOnly />
        ) : graph.isError ? (
          isNotFound ? (
            <EmptyState
              icon={<FileSearch className="h-6 w-6" aria-hidden />}
              title="No graph available for this contract"
              description="The graph endpoint returned no data (404) for this contract — it may not have been analyzed yet, or analysis produced no graph."
              action={
                <Button variant="outline" size="sm" onClick={retry}>
                  <RefreshCw className="h-3.5 w-3.5" aria-hidden /> Retry
                </Button>
              }
            />
          ) : (
            <ErrorState
              title="Failed to load the graph"
              description={isApiError(graphError) ? graphError.detail : graphError?.message}
              action={
                <Button variant="outline" size="sm" onClick={retry}>
                  <RefreshCw className="h-3.5 w-3.5" aria-hidden /> Retry
                </Button>
              }
            />
          )
        ) : !selected ? (
          <EmptyState
            title="Pick a contract"
            description="Choose a completed contract above, or paste a contract_id to load its graph."
          />
        ) : (
          <GraphCanvas snapshot={graph.data} isLoading={false} />
        )}
      </main>

      <Disclaimer />
    </div>
  );
}
