'use client';

import * as React from 'react';
import { AlertTriangle, GitCompareArrows, Info } from 'lucide-react';

import { Disclaimer } from '@/components/layout/disclaimer';
import {
  ClauseDiffCard,
  ObligationList,
  RiskList,
  SectionCard,
} from '@/components/comparison/sections';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Separator } from '@/components/ui/separator';
import { EmptyState, LoadingState } from '@/components/ui/state';
import { SeverityBadge } from '@/components/risks/badges';
import {
  useClauses,
  useContractSummary,
  useObligations,
  useRecentContracts,
  useRisks,
} from '@/features/analysis/use-analysis';
import {
  diffObligations,
  diffRisks,
  findPossibleConflicts,
  matchClauses,
} from '@/features/comparison/compare';
import { isApiError } from '@/lib/api/errors';
import type { JobInfo } from '@/types';

/** All four data slices for one contract, plus an explicit completeness flag. */
function useContractData(id: string | null) {
  const summary = useContractSummary(id);
  const clauses = useClauses(id);
  const risks = useRisks(id);
  const obligations = useObligations(id);

  const pending = summary.isLoading || clauses.isLoading || risks.isLoading || obligations.isLoading;
  const failed =
    summary.isError || clauses.isError || risks.isError || obligations.isError;
  const incomplete =
    failed ||
    !summary.data ||
    (clauses.data?.clauses?.length ?? 0) === 0 ||
    (risks.data?.risks?.length ?? 0) === 0 ||
    (obligations.data?.obligations?.length ?? 0) === 0;

  return { summary, clauses, risks, obligations, pending, incomplete };
}

function ContractPicker({
  label,
  value,
  onChange,
  contracts,
  loading,
  excludeId,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  contracts: { id: string; title: string }[];
  loading: boolean;
  excludeId?: string;
}) {
  const [manual, setManual] = React.useState('');
  const isManual = value && !contracts.some((c) => c.id === value);
  return (
    <label className="flex min-w-[240px] flex-1 flex-col gap-1.5 sm:max-w-sm">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={loading}
        className="h-9 rounded-md border border-input bg-background px-3 py-1 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
      >
        {loading ? (
          <option value="">Loading…</option>
        ) : (
          <>
            <option value="">— select —</option>
            {contracts.map((c) => (
              <option key={c.id} value={c.id} disabled={c.id === excludeId}>
                {c.title} — {c.id}
              </option>
            ))}
            {isManual ? <option value={value}>{value} (manual)</option> : null}
          </>
        )}
      </select>
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          const v = manual.trim();
          if (v) onChange(v);
          setManual('');
        }}
      >
        <Input value={manual} onChange={(e) => setManual(e.target.value)} placeholder="…or paste contract_id" className="h-8 text-xs" />
        <Button type="submit" variant="ghost" size="sm">Set</Button>
      </form>
    </label>
  );
}

function ContractSummaryRow({ data, id }: { data: ReturnType<typeof useContractData>; id: string }) {
  if (data.pending) return <LoadingState label="Loading contract data…" />;
  if (data.incomplete) {
    const errors = [data.summary.error, data.clauses.error, data.risks.error, data.obligations.error];
    const detail =
      errors.find((e) => isApiError(e))?.message ?? 'some data was empty or failed to load';
    return (
      <div className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" aria-hidden />
        <div>
          <p className="font-medium text-destructive">Data unavailable or incomplete for {id}</p>
          <p className="text-xs text-muted-foreground">{detail} — compare needs complete data on both sides.</p>
        </div>
      </div>
    );
  }
  const s = data.summary.data;
  const clauses = data.clauses.data;
  const risks = data.risks.data;
  const obligations = data.obligations.data;
  if (!s || !clauses || !risks || !obligations) {
    return <p className="text-xs text-muted-foreground">Incomplete data.</p>;
  }
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-md border bg-card p-3 text-sm">
      <span className="font-medium">{s.title}</span>
      <span className="font-mono text-xs text-muted-foreground">{s.contract_id}</span>
      <SeverityBadge severity={s.overall_risk_level} />
      <span className="text-xs text-muted-foreground">score {s.overall_risk_score}</span>
      <span className="text-xs text-muted-foreground">{clauses.clauses.length} clauses</span>
      <span className="text-xs text-muted-foreground">{risks.risks.length} risks</span>
      <span className="text-xs text-muted-foreground">{obligations.obligations.length} obligations</span>
    </div>
  );
}

export default function ComparePage() {
  const { data, isLoading: loadingContracts } = useRecentContracts();
  const contracts = React.useMemo(() => {
    const jobs = (data?.jobs ?? []).filter((j: JobInfo) => j.result !== null && j.result !== undefined);
    const seen = new Set<string>();
    const out: { id: string; title: string }[] = [];
    for (const job of jobs) {
      if (seen.has(job.contract_id)) continue;
      seen.add(job.contract_id);
      out.push({ id: job.contract_id, title: job.result?.contract?.title ?? job.contract_id });
    }
    return out;
  }, [data]);

  const [a, setA] = React.useState('');
  const [b, setB] = React.useState('');
  // Default to the first two distinct contracts once available.
  React.useEffect(() => {
    if (contracts.length >= 2) {
      if (!a) setA(contracts[0].id);
      if (!b) setB(contracts[1].id);
    }
  }, [contracts, a, b]);

  const distinct = !!a && !!b && a !== b;
  const dataA = useContractData(distinct ? a : null);
  const dataB = useContractData(distinct ? b : null);

  const bothReady = distinct && !dataA.pending && !dataB.pending && !dataA.incomplete && !dataB.incomplete;

  const result = React.useMemo(() => {
    if (!bothReady) return null;
    const aClauses = dataA.clauses.data!.clauses;
    const bClauses = dataB.clauses.data!.clauses;
    const aRisks = dataA.risks.data!.risks;
    const bRisks = dataB.risks.data!.risks;
    const matches = matchClauses(aClauses, bClauses);
    const counts = {
      added: matches.filter((m) => m.kind === 'added').length,
      removed: matches.filter((m) => m.kind === 'removed').length,
      modified: matches.filter((m) => m.kind === 'modified').length,
      unchanged: matches.filter((m) => m.kind === 'unchanged').length,
    };
    const risks = diffRisks(aRisks, bRisks);
    const obligations = diffObligations(dataA.obligations.data!.obligations, dataB.obligations.data!.obligations);
    const conflicts = findPossibleConflicts(matches, aRisks, bRisks);
    return { matches, counts, risks, obligations, conflicts };
  }, [bothReady, dataA, dataB]);

  const unchangedMatches = result ? result.matches.filter((m) => m.kind === 'unchanged') : [];

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="flex items-center gap-2 font-display text-2xl font-semibold tracking-tight">
          <GitCompareArrows className="h-5 w-5 text-muted-foreground" aria-hidden /> Contract Comparison
        </h1>
        <div className="flex items-start gap-2 rounded-md border border-primary/20 bg-primary/5 px-3 py-2 text-xs text-foreground">
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" aria-hidden />
          <span>
            The backend has <strong>no comparison endpoint</strong>. Comparison is computed entirely in the
            browser from both contracts&apos; stored analysis (summary, clauses, obligations, risks).
          </span>
        </div>
      </header>

      <Card>
        <CardContent className="pt-5">
          <div className="flex flex-wrap items-start gap-4">
            <ContractPicker label="Contract A" value={a} onChange={setA} contracts={contracts} loading={loadingContracts} excludeId={b} />
            <ContractPicker label="Contract B" value={b} onChange={setB} contracts={contracts} loading={loadingContracts} excludeId={a} />
          </div>
          {a && b && a === b ? (
            <p className="mt-3 text-xs text-destructive">Pick two different contracts to compare.</p>
          ) : null}
        </CardContent>
      </Card>

      <Separator />

      {!distinct ? (
        <EmptyState
          icon={<GitCompareArrows className="h-6 w-6" aria-hidden />}
          title="Select two contracts"
          description={
            loadingContracts
              ? 'Loading recent contracts…'
              : contracts.length === 0
                ? 'No completed contracts yet — upload at least two first.'
                : 'Choose contracts A and B (or paste contract_ids) above to run the comparison.'
          }
        />
      ) : dataA.pending || dataB.pending ? (
        <LoadingState label="Fetching both contracts' analysis…" className="py-10 justify-center" />
      ) : !bothReady ? (
        <div className="space-y-3">
          <h2 className="text-sm font-medium text-muted-foreground">
            Cannot compare — data is not complete on both sides
          </h2>
          <div className="grid gap-3 lg:grid-cols-2">
            <div className="space-y-2">
              <p className="text-xs font-medium text-muted-foreground">A — {a}</p>
              <ContractSummaryRow data={dataA} id={a} />
            </div>
            <div className="space-y-2">
              <p className="text-xs font-medium text-muted-foreground">B — {b}</p>
              <ContractSummaryRow data={dataB} id={b} />
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            Clause, risk and obligation diffs are only computed when all four data slices load with non-empty
            results for both contracts — partial outputs are never compared.
          </p>
        </div>
      ) : result ? (
        <div className="space-y-4">
          <div className="grid gap-3 lg:grid-cols-2">
            <div className="space-y-2">
              <p className="text-xs font-medium text-muted-foreground">A</p>
              <ContractSummaryRow data={dataA} id={a} />
            </div>
            <div className="space-y-2">
              <p className="text-xs font-medium text-muted-foreground">B</p>
              <ContractSummaryRow data={dataB} id={b} />
            </div>
          </div>

          <SectionCard
            title={`Clause differences (${result.matches.length} total)`}
            description="Matched by section number, then heading, then ordinal position. Added/removed/modified shown in full; unchanged collapsed to a count."
          >
            <div className="flex flex-wrap gap-2 text-xs">
              <span className="rounded-full bg-risk-low/15 px-2.5 py-1 text-risk-low">+{result.counts.added} added in B</span>
              <span className="rounded-full bg-destructive/10 px-2.5 py-1 text-destructive">−{result.counts.removed} removed in B</span>
              <span className="rounded-full bg-secondary px-2.5 py-1">~{result.counts.modified} modified</span>
              <span className="rounded-full bg-muted px-2.5 py-1 text-muted-foreground">={result.counts.unchanged} unchanged</span>
            </div>
            <div className="space-y-2">
              {result.matches
                .filter((m) => m.kind !== 'unchanged')
                .map((m, i) => (
                  <ClauseDiffCard key={`${m.a?.clause_id ?? 'a'}-${m.b?.clause_id ?? 'b'}-${i}`} match={m} />
                ))}
              {unchangedMatches.length > 0 ? (
                <details className="rounded-md border px-3 py-2 text-sm">
                  <summary className="cursor-pointer text-xs text-muted-foreground">
                    {unchangedMatches.length} unchanged clauses (expand)
                  </summary>
                  <div className="mt-2 space-y-2">
                    {unchangedMatches.map((m, i) => (
                      <ClauseDiffCard key={`u-${i}`} match={m} />
                    ))}
                  </div>
                </details>
              ) : null}
            </div>
          </SectionCard>

          <SectionCard
            title={`Risk differences (${result.risks.added.length} new, ${result.risks.removed.length} removed)`}
            description="Matched by rule_id + clause_id. 'New' = in B only; 'Removed' = in A only. Severity changes are listed separately."
          >
            <div className="grid gap-4 lg:grid-cols-2">
              <div className="space-y-2">
                <h4 className="text-xs font-medium text-destructive">Removed findings (in A, not in B)</h4>
                <RiskList risks={result.risks.removed} emptyLabel="None." />
              </div>
              <div className="space-y-2">
                <h4 className="text-xs font-medium text-risk-low">New findings (in B, not in A)</h4>
                <RiskList risks={result.risks.added} emptyLabel="None." />
              </div>
            </div>
            {result.risks.severityChanges.length > 0 ? (
              <div className="space-y-2">
                <h4 className="text-xs font-medium text-muted-foreground">Severity changes (same rule in both, different severity)</h4>
                <ul className="space-y-2">
                  {result.risks.severityChanges.map((c) => (
                    <li key={`${c.ruleId}-${c.clauseId ?? ''}`} className="flex items-center justify-between gap-3 rounded-md border bg-card p-3">
                      <div className="min-w-0">
                        <p className="text-sm font-medium">{c.name}</p>
                        <p className="mt-0.5 font-mono text-[11px] text-muted-foreground">{c.ruleId}{c.clauseId ? ` · ${c.clauseId}` : ''}</p>
                      </div>
                      <div className="flex items-center gap-2 text-xs">
                        <SeverityBadge severity={c.a?.severity ?? ''} />
                        <span className="text-muted-foreground">→</span>
                        <SeverityBadge severity={c.b?.severity ?? ''} />
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </SectionCard>

          <SectionCard
            title={`Obligation differences (${result.obligations.countA} → ${result.obligations.countB})`}
            description="Matched by obligation_id, falling back to subject + action + object + type."
          >
            <div className="grid gap-4 lg:grid-cols-2">
              <div className="space-y-2">
                <h4 className="text-xs font-medium text-destructive">Removed ({result.obligations.removed.length})</h4>
                <ObligationList obligations={result.obligations.removed} side="A" />
              </div>
              <div className="space-y-2">
                <h4 className="text-xs font-medium text-risk-low">Added ({result.obligations.added.length})</h4>
                <ObligationList obligations={result.obligations.added} side="B" />
              </div>
            </div>
          </SectionCard>

          <SectionCard
            title={`Possible conflicts (${result.conflicts.length})`}
            description="A modified clause that carries a risk in A and a different risk in B. Heuristic only — flagged as 'possible conflict, needs review', never asserted."
          >
            {result.conflicts.length === 0 ? (
              <p className="text-sm text-muted-foreground">None detected.</p>
            ) : (
              <ul className="space-y-2">
                {result.conflicts.map((c, i) => (
                  <li key={i} className="rounded-md border border-risk-medium/40 bg-risk-medium/10 p-3 text-sm">
                    <div className="flex items-start gap-2">
                      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-risk-medium" aria-hidden />
                      <div className="min-w-0 flex-1">
                        <p className="font-medium">
                          {c.clause.a ? c.clause.a.section_number || c.clause.a.heading || c.clause.a.clause_id : 'Clause'}
                          <span className="ml-2 text-xs font-normal text-muted-foreground">
                            possible conflict, needs review
                          </span>
                        </p>
                        <p className="mt-1 text-xs text-muted-foreground">
                          Provision text changed between A and B; the clause was risked differently in each.
                        </p>
                        <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
                          <span className="text-muted-foreground">A:</span>
                          <span>{c.aRisk.name}</span>
                          <SeverityBadge severity={c.aRisk.severity} />
                          <span className="ml-2 text-muted-foreground">B:</span>
                          <span>{c.bRisk.name}</span>
                          <SeverityBadge severity={c.bRisk.severity} />
                        </div>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </SectionCard>
        </div>
      ) : null}

      <Disclaimer />
    </div>
  );
}
