'use client';

import * as React from 'react';
import { Plus, Minus, Pencil, Check } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { SeverityBadge } from '@/components/risks/badges';
import type { Clause, Obligation, RiskFlag } from '@/types';
import { textDiff, type ClauseMatch, type ObligationDiff, type RiskDiff } from '@/features/comparison/compare';

function clauseTitle(c: Clause): string {
  return c.section_number || c.heading || `Clause ${c.clause_id}`;
}

function TextDiff({ a, b }: { a: string; b: string }) {
  const segs = React.useMemo(() => textDiff(a, b), [a, b]);
  return (
    <p className="whitespace-pre-wrap break-words text-xs leading-relaxed">
      {segs.map((s, i) =>
        s.added ? (
          <ins key={i} className="bg-risk-low/15 text-risk-low no-underline" title="Added in B">
            {s.value}
          </ins>
        ) : s.removed ? (
          <del key={i} className="bg-destructive/10 text-destructive" title="Removed from A">
            {s.value}
          </del>
        ) : (
          <span key={i}>{s.value}</span>
        )
      )}
    </p>
  );
}

export function ClauseDiffCard({ match }: { match: ClauseMatch }) {
  const [open, setOpen] = React.useState(match.kind !== 'unchanged');
  const title = match.a ? clauseTitle(match.a) : match.b ? clauseTitle(match.b) : 'Clause';

  const chip =
    match.kind === 'added' ? (
      <Badge className="bg-risk-low/15 text-risk-low border-risk-low/30"><Plus className="h-3 w-3" aria-hidden /> Added in B</Badge>
    ) : match.kind === 'removed' ? (
      <Badge className="bg-destructive/10 text-destructive border-destructive/30"><Minus className="h-3 w-3" aria-hidden /> Removed in B</Badge>
    ) : match.kind === 'modified' ? (
      <Badge variant="secondary"><Pencil className="h-3 w-3" aria-hidden /> Modified</Badge>
    ) : (
      <Badge variant="outline"><Check className="h-3 w-3" aria-hidden /> Unchanged</Badge>
    );

  return (
    <div className="rounded-lg border bg-card">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-3 px-4 py-2.5 text-left"
      >
        <span className="line-clamp-1 text-sm font-medium">{title}</span>
        <span className="flex items-center gap-2">
          <span className="text-[10px] text-muted-foreground">matched by {match.matchBasis}</span>
          {chip}
        </span>
      </button>

      {open ? (
        <div className="border-t px-4 py-3">
          {match.a && match.b ? (
            <div className="grid gap-4 lg:grid-cols-2">
              <div className="rounded-md bg-muted/30 p-3">
                <p className="mb-1.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">A</p>
                {match.kind === 'modified' ? <TextDiff a={match.a.text} b={match.b.text} /> : <p className="whitespace-pre-wrap break-words text-xs">{match.a.text}</p>}
              </div>
              <div className="rounded-md bg-muted/30 p-3">
                <p className="mb-1.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">B</p>
                <p className="whitespace-pre-wrap break-words text-xs">{match.b.text}</p>
              </div>
            </div>
          ) : match.a ? (
            <div className="rounded-md bg-destructive/5 p-3">
              <p className="mb-1.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">Only in A</p>
              <p className="whitespace-pre-wrap break-words text-xs">{match.a.text}</p>
            </div>
          ) : match.b ? (
            <div className="rounded-md bg-risk-low/10 p-3">
              <p className="mb-1.5 text-[10px] font-medium uppercase tracking-wide text-risk-low">Only in B</p>
              <p className="whitespace-pre-wrap break-words text-xs">{match.b.text}</p>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export function RiskList({ risks, emptyLabel }: { risks: RiskFlag[]; emptyLabel: string }) {
  if (risks.length === 0) return <p className="text-sm text-muted-foreground">{emptyLabel}</p>;
  return (
    <ul className="space-y-2">
      {risks.map((r) => (
        <li key={r.risk_id} className="flex items-start justify-between gap-3 rounded-md border bg-card p-3">
          <div className="min-w-0">
            <p className="text-sm font-medium">{r.name}</p>
            <p className="mt-0.5 font-mono text-[11px] text-muted-foreground">{r.rule_id}{r.clause_id ? ` · ${r.clause_id}` : ' · contract-level'}</p>
          </div>
          <SeverityBadge severity={r.severity} className="shrink-0" />
        </li>
      ))}
    </ul>
  );
}

export function ObligationList({ obligations, side }: { obligations: Obligation[]; side: 'A' | 'B' }) {
  if (obligations.length === 0) return <p className="text-sm text-muted-foreground">None.</p>;
  return (
    <ul className="space-y-2">
      {obligations.map((o) => (
        <li key={`${side}-${o.obligation_id}`} className="rounded-md border bg-card p-3 text-sm">
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="text-[11px]">{o.obligation_type}</Badge>
            {o.subject ? <span className="text-xs text-muted-foreground">{o.subject}</span> : null}
          </div>
          <p className="mt-1.5 break-words text-xs">{o.text}</p>
        </li>
      ))}
    </ul>
  );
}

export function SectionCard({
  title,
  description,
  children,
  className,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
        {description ? <CardDescription>{description}</CardDescription> : null}
      </CardHeader>
      <CardContent className="space-y-3">{children}</CardContent>
    </Card>
  );
}
