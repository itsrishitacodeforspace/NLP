'use client';

import * as React from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import {
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  EmptyState,
  ErrorState,
  LoadingState,
} from '@/components/ui/state';
import { Separator } from '@/components/ui/separator';
import { Disclaimer } from '@/components/layout/disclaimer';
import { RiskGauge, SeverityBadge, SourceBadge } from '@/components/risks/badges';
import { useContractSummary, useRisks } from '@/features/analysis/use-analysis';
import {
  buildComplianceIndicators,
  COMPLIANCE_STATUS_STYLE,
  countBySeverity,
  groupByCategorySeverities,
  scoreBreakdownFindings,
  scoreBreakdownTerms,
} from '@/features/risks';
import { SEVERITY_META, SEVERITY_ORDER, toSeverity } from '@/lib/severity';
import { cn } from '@/lib/utils';
import type { RiskFlag } from '@/types';

/* ------------------------------------------------------------------ */
/* Score breakdown                                                     */
/* ------------------------------------------------------------------ */

const BREAKDOWN_TERM_LABEL: Record<string, string> = {
  top: 'Top finding',
  volume: 'Finding volume',
  severity_mass: 'Severity mass',
  cap_adjustment: 'Cap adjustment',
};

function ScoreBreakdownCard({
  breakdown,
  caveat,
}: {
  breakdown: Record<string, unknown> | null | undefined;
  caveat?: string | null;
}) {
  const terms = scoreBreakdownTerms(breakdown);
  const findings = scoreBreakdownFindings(breakdown);
  if (terms.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Score breakdown</CardTitle>
          <CardDescription>Why the contract received this score</CardDescription>
        </CardHeader>
        <CardContent>
          <EmptyState
            title="No breakdown available"
            description="The backend did not return a score breakdown for this contract."
          />
        </CardContent>
      </Card>
    );
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle>Score breakdown</CardTitle>
        <CardDescription>
          How the overall score was assembled from the findings.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {terms.map(({ term, value }) => (
            <div key={term} className="rounded-md border bg-muted/30 px-3 py-2">
              <div className="text-xs text-muted-foreground">{BREAKDOWN_TERM_LABEL[term] ?? term}</div>
              <div className={cn('text-lg font-semibold', value < 0 && 'text-muted-foreground')}>
                {value > 0 && term === 'top' ? value : value}
              </div>
            </div>
          ))}
        </div>
        <div>
          <div className="mb-1.5 text-xs font-medium text-muted-foreground">Findings by severity</div>
          <div className="flex flex-wrap gap-1.5">
            {SEVERITY_ORDER.filter((s) => s !== 'informational').map((sev) => (
              <Badge
                key={sev}
                variant="outline"
                className={cn('gap-1', SEVERITY_META[sev].text, SEVERITY_META[sev].border)}
              >
                {SEVERITY_META[sev].label}
                <span className="tabular-nums">{findings[sev as 'critical' | 'high' | 'medium' | 'low']}</span>
              </Badge>
            ))}
          </div>
        </div>
        {caveat ? (
          <p className="text-xs text-muted-foreground">{caveat}</p>
        ) : null}
      </CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Severity donut                                                      */
/* ------------------------------------------------------------------ */

function SeverityDonut({ risks }: { risks: RiskFlag[] }) {
  const counts = countBySeverity(risks);
  const data = SEVERITY_ORDER.filter((s) => s !== 'informational')
    .map((sev) => ({ name: SEVERITY_META[sev].label, value: counts[sev as 'critical' | 'high' | 'medium' | 'low'], hex: SEVERITY_META[sev].hex }))
    .filter((d) => d.value > 0);
  const total = data.reduce((n, d) => n + d.value, 0);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Severity distribution</CardTitle>
        <CardDescription>{total} finding{total === 1 ? '' : 's'} by severity</CardDescription>
      </CardHeader>
      <CardContent>
        {total === 0 ? (
          <EmptyState title="No risks found" description="No risk findings were raised for this contract." />
        ) : (
          <div className="flex items-center gap-4">
            <div className="h-48 w-48 shrink-0">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={data} dataKey="value" nameKey="name" innerRadius={45} outerRadius={75} paddingAngle={2} strokeWidth={0}>
                    {data.map((d) => (
                      <Cell key={d.name} fill={d.hex} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <ul className="space-y-1.5 text-sm">
              {data.map((d) => (
                <li key={d.name} className="flex items-center gap-2">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: d.hex }} aria-hidden />
                  <span className="text-muted-foreground">{d.name}</span>
                  <span className="ml-auto tabular-nums font-medium">{d.value}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Category breakdown + heatmap                                        */
/* ------------------------------------------------------------------ */

function CategoryBreakdown({ risks }: { risks: RiskFlag[] }) {
  const groups = groupByCategorySeverities(risks);
  const max = Math.max(1, ...groups.map((g) => g.total));
  const data = groups.map((g) => ({ name: g.category, count: g.total }));
  return (
    <Card>
      <CardHeader>
        <CardTitle>Findings by category</CardTitle>
        <CardDescription>
          Frontend grouping by <code className="text-xs">rule_id</code> prefix — not a backend category.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {groups.length === 0 ? (
          <EmptyState title="No categories" description="Nothing to group yet." />
        ) : (
          <div className="h-56 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data} layout="vertical" margin={{ left: 8, right: 24 }}>
                <XAxis type="number" hide />
                <YAxis type="category" dataKey="name" width={130} tickLine={false} axisLine={false} tick={{ fontSize: 12 }} />
                <Tooltip cursor={{ fill: 'rgba(0,0,0,0.04)' }} />
                <Bar dataKey="count" name="Findings" fill="#3b82f6" radius={[0, 4, 4, 0]} barSize={16} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
        {/* Simple bar list fallback is redundant; keep the chart above. */}
        {groups.length > 0 ? (
          <ul className="mt-3 space-y-1">
            {groups.map((g) => (
              <li key={g.category} className="flex items-center gap-2 text-sm">
                <span className="w-32 shrink-0 truncate text-muted-foreground" title={g.category}>
                  {g.category}
                </span>
                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
                  <div className="h-full rounded-full bg-primary/70" style={{ width: `${(g.total / max) * 100}%` }} />
                </div>
                <span className="w-6 text-right tabular-nums">{g.total}</span>
              </li>
            ))}
          </ul>
        ) : null}
      </CardContent>
    </Card>
  );
}

function CategoryHeatmap({ risks }: { risks: RiskFlag[] }) {
  const groups = groupByCategorySeverities(risks);
  const sevs = (['critical', 'high', 'medium', 'low'] as const);
  const maxCell = Math.max(1, ...groups.flatMap((g) => sevs.map((s) => g.counts[s])));
  return (
    <Card>
      <CardHeader>
        <CardTitle>Category × severity</CardTitle>
        <CardDescription>Count of findings per category and severity</CardDescription>
      </CardHeader>
      <CardContent>
        {groups.length === 0 ? (
          <EmptyState title="No data" description="No findings to heat-map." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr>
                  <th className="pb-2 pr-3 text-left font-medium text-muted-foreground">Category</th>
                  {sevs.map((s) => (
                    <th key={s} className="pb-2 px-2 text-center font-medium text-muted-foreground">
                      {SEVERITY_META[s].label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {groups.map((g) => (
                  <tr key={g.category}>
                    <td className="pr-3 py-1 text-muted-foreground">{g.category}</td>
                    {sevs.map((s) => {
                      const n = g.counts[s];
                      const alpha = n === 0 ? 0 : 0.15 + 0.85 * (n / maxCell);
                      return (
                        <td key={s} className="px-1 py-1 text-center">
                          <span
                            className="inline-flex h-7 w-9 items-center justify-center rounded text-xs tabular-nums"
                            style={
                              n === 0
                                ? undefined
                                : {
                                    backgroundColor: `${SEVERITY_META[s].hex}${Math.round(alpha * 255)
                                      .toString(16)
                                      .padStart(2, '0')}`,
                                    color: alpha > 0.5 ? '#fff' : undefined,
                                  }
                            }
                          >
                            {n || '·'}
                          </span>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Review checklist (local state only)                                 */
/* ------------------------------------------------------------------ */

function ReviewChecklist({ risks }: { risks: RiskFlag[] }) {
  const [checked, setChecked] = React.useState<Set<string>>(new Set());
  const items = React.useMemo(
    () =>
      risks
        .filter((r) => r.severity === 'high' || r.severity === 'critical')
        .sort((a, b) => b.score - a.score),
    [risks]
  );
  const toggle = (id: string) =>
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  const done = items.filter((i) => checked.has(i.risk_id)).length;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Must review before signing</CardTitle>
        <CardDescription>
          Your review checklist — high &amp; critical findings only. Stored locally in this
          browser tab; nothing is persisted or sent to the backend.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <EmptyState title="No high/critical findings" description="No findings require mandatory review." />
        ) : (
          <ul className="space-y-2">
            <li className="text-xs text-muted-foreground">
              {done} of {items.length} reviewed
            </li>
            {items.map((r) => {
              const id = r.risk_id;
              const isChecked = checked.has(id);
              return (
                <li key={id}>
                  <label className="flex cursor-pointer items-start gap-2.5 rounded-md border px-3 py-2 hover:bg-muted/40">
                    <input
                      type="checkbox"
                      checked={isChecked}
                      onChange={() => toggle(id)}
                      className="mt-0.5 h-4 w-4 rounded border-input accent-primary"
                    />
                    <span className="min-w-0 flex-1">
                      <span className={cn('flex flex-wrap items-center gap-1.5', isChecked && 'text-muted-foreground line-through')}>
                        <SeverityBadge severity={r.severity} />
                        <span className="text-sm font-medium">{r.name}</span>
                        <span className="text-xs text-muted-foreground">{r.rule_id}</span>
                      </span>
                      <span className="mt-0.5 block text-xs text-muted-foreground">{r.explanation}</span>
                    </span>
                  </label>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Findings grouped by severity                                        */
/* ------------------------------------------------------------------ */

function FindingsBySeverity({ risks, contractId }: { risks: RiskFlag[]; contractId: string }) {
  const [open, setOpen] = React.useState<Record<string, boolean>>({
    critical: true,
    high: true,
  });
  const ordered = SEVERITY_ORDER.filter((s) => s !== 'informational')
    .map((sev) => ({ sev, items: risks.filter((r) => toSeverity(r.severity) === sev) }))
    .filter((g) => g.items.length > 0);

  return (
    <Card>
      <CardHeader>
        <CardTitle>All findings</CardTitle>
        <CardDescription>
          {risks.length} finding{risks.length === 1 ? '' : 's'}, grouped by severity.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {ordered.length === 0 ? (
          <EmptyState title="No risks found" description="No risk findings were raised for this contract." />
        ) : (
          <div className="space-y-3">
            {ordered.map(({ sev, items }) => (
              <div key={sev} className="rounded-md border">
                <button
                  type="button"
                  onClick={() => setOpen((p) => ({ ...p, [sev]: !p[sev] }))}
                  className="flex w-full items-center gap-2 px-3 py-2 text-left"
                >
                  <span className={cn('text-xs', open[sev] ? 'rotate-90' : '', 'transition-transform', 'inline-block')}>
                    ▸
                  </span>
                  <SeverityBadge severity={sev} />
                  <span className="text-sm text-muted-foreground">
                    {items.length} finding{items.length === 1 ? '' : 's'}
                  </span>
                </button>
                {open[sev] ? (
                  <ul className="divide-y border-t">
                    {items.map((r) => (
                      <li key={r.risk_id} className="flex items-start gap-3 px-3 py-2.5">
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-1.5">
                            <span className="text-sm font-medium">{r.name}</span>
                            <SeverityBadge severity={r.severity} />
                            <SourceBadge source={r.source} evidenceStatus={r.evidence_status} />
                          </div>
                          <div className="mt-0.5 text-xs text-muted-foreground">
                            {r.rule_id}
                            {r.clause_id ? ` · clause ${r.clause_id}` : ''}
                          </div>
                          <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{r.explanation}</p>
                        </div>
                        <Link
                          href={`/contracts/${contractId}/review`}
                          className="mt-0.5 shrink-0 text-xs text-primary underline-offset-2 hover:underline"
                        >
                          View in review →
                        </Link>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Compliance indicators                                               */
/* ------------------------------------------------------------------ */

function ComplianceGrid({ contractId }: { contractId: string }) {
  const summaryQ = useContractSummary(contractId);
  const risksQ = useRisks(contractId);
  if (summaryQ.isPending || risksQ.isPending) {
    return <LoadingState label="Evaluating compliance indicators…" className="p-5" />;
  }
  if (summaryQ.isError || risksQ.isError) return null; // page-level error already shown
  const indicators = buildComplianceIndicators(summaryQ.data, risksQ.data.risks);
  return (
    <Card>
      <CardHeader>
        <CardTitle>Compliance indicators</CardTitle>
        <CardDescription>
          Derived from real backend signals only (risk findings, missing clauses,
          detected values). Never a pass/fail verdict.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {indicators.map((ind) => {
            const style = COMPLIANCE_STATUS_STYLE[ind.status];
            return (
              <div key={ind.label} title={ind.note} className={cn('flex items-center justify-between gap-2 rounded-md border px-3 py-2', style.chip)}>
                <span className="text-sm">{ind.label}</span>
                <span className={cn('text-xs font-medium', style.text)}>{ind.status}</span>
              </div>
            );
          })}
        </div>
        <Separator className="my-3" />
        <p className="text-xs text-muted-foreground">
          Absence of a finding is not a compliance certification. “Not detected” and “Not
          evaluated” are neutral states — they do not indicate the contract complies.
        </p>
      </CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

export default function RisksPage() {
  const params = useParams<{ contractId: string }>();
  const contractId = params?.contractId as string | undefined;
  const summaryQ = useContractSummary(contractId);
  const risksQ = useRisks(contractId);

  if (!contractId) {
    return <ErrorState title="Missing contract ID" description="No contract ID in the URL." />;
  }
  if (summaryQ.isPending || risksQ.isPending) {
    return <LoadingState label="Loading risk dashboard…" className="p-10" />;
  }
  if (summaryQ.isError || risksQ.isError) {
    const err = (summaryQ.error ?? risksQ.error) as { message?: string } | null;
    return (
      <div className="space-y-4 p-6">
        <ErrorState
          title="Could not load risk dashboard"
          description={err?.message ?? 'The contract may not exist or analysis is incomplete.'}
        />
        <Disclaimer />
      </div>
    );
  }

  const summary = summaryQ.data;
  const risks = risksQ.data.risks;

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Risk dashboard</h1>
        <p className="text-sm text-muted-foreground">
          {summary.title}
          {summary.parties && summary.parties.length > 0 ? (
            <> · {summary.parties.join(' · ')}</>
          ) : null}
        </p>
      </header>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Overall risk</CardTitle>
            <CardDescription>
              {summary.clause_count} clauses · {risks.length} finding{risks.length === 1 ? '' : 's'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <RiskGauge
              score={summary.overall_risk_score}
              level={summary.overall_risk_level}
              caveat={summary.score_caveat ?? undefined}
            />
          </CardContent>
        </Card>
        <div className="lg:col-span-2">
          <ScoreBreakdownCard breakdown={summary.risk_score_breakdown} caveat={summary.score_caveat} />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <SeverityDonut risks={risks} />
        <CategoryBreakdown risks={risks} />
      </div>

      <CategoryHeatmap risks={risks} />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ReviewChecklist risks={risks} />
        <ComplianceGrid contractId={contractId} />
      </div>

      <FindingsBySeverity risks={risks} contractId={contractId} />

      <Disclaimer />
    </div>
  );
}
