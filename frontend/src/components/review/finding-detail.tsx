'use client';

import * as React from 'react';
import {
  ArrowUpRight,
  Gavel,
  Info,
  MousePointerClick,
  Quote,
  ShieldAlert,
  Target,
  Users,
} from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { EmptyState } from '@/components/ui/state';
import { SeverityBadge, SourceBadge } from '@/components/risks/badges';
import { toSeverity } from '@/lib/severity';
import type { CaseLawReference, RiskFlag } from '@/types';

interface FindingDetailProps {
  risk: RiskFlag | null;
  /** Called when the user wants the left pane to jump to a clause. */
  onGoToClause: (clauseId: string) => void;
  hasRisks: boolean;
}

function FieldLabel({ icon, children }: { icon?: React.ReactNode; children: React.ReactNode }) {
  return (
    <h3 className="flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-[0.14em] text-muted-foreground">
      {icon}
      {children}
    </h3>
  );
}

function CaseLawEntry({ entry }: { entry: CaseLawReference }) {
  const verified = entry.verified_on != null;
  return (
    <li className="border-l-2 border-border py-1 pl-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-display text-sm font-semibold text-foreground">{entry.citation}</span>
        {verified ? (
          <Badge variant="outline" className="gap-1 border-risk-low/40 text-risk-low">
            <Gavel className="h-3 w-3" aria-hidden />
            Verified {entry.verified_on}
          </Badge>
        ) : (
          <Badge variant="outline" className="gap-1 border-destructive/40 text-destructive">
            Unverified reference — not independently checked
          </Badge>
        )}
        <Badge variant="secondary">{entry.jurisdiction}</Badge>
      </div>
      <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{entry.summary}</p>
      {!verified ? (
        <p className="mt-1 text-xs leading-relaxed text-destructive">
          This citation has not been verified against primary text. Confirm with counsel before relying on it.
        </p>
      ) : null}
      {entry.verify_note ? (
        <p className="mt-1 text-xs italic text-muted-foreground">{entry.verify_note}</p>
      ) : null}
    </li>
  );
}

export function FindingDetail({ risk, onGoToClause, hasRisks }: FindingDetailProps) {
  if (!risk) {
    return (
      <EmptyState
        icon={<MousePointerClick className="h-8 w-8" aria-hidden />}
        title={hasRisks ? 'Select a finding to see details' : 'No risk findings'}
        description={
          hasRisks
            ? 'Click a highlighted passage in the document or an item in the findings list to inspect its explanation, evidence, and suggested review action.'
            : 'No risk findings were produced for this contract.'
        }
        className="h-full"
      />
    );
  }

  const severity = toSeverity(risk.severity);
  const highSeverity = severity === 'critical' || severity === 'high';
  const evidenceSpans = risk.evidence_spans ?? [];
  const evidenceUnbound = risk.evidence_status === 'unverified' || risk.evidence_status === 'unavailable';

  return (
    <Card className="flex h-full min-h-0 flex-col">
      <CardHeader className="space-y-2.5">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="font-display text-lg font-semibold leading-tight tracking-tight">{risk.name}</h2>
          <SeverityBadge severity={risk.severity} />
          <SourceBadge source={risk.source} evidenceStatus={risk.evidence_status} />
        </div>
        {risk.clause_id ? (
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span className="max-w-full truncate font-mono text-[11px]" title={risk.clause_id}>
              {risk.clause_id}
            </span>
            <Button
              size="sm"
              variant="outline"
              className="h-7 gap-1 px-2 text-xs"
              onClick={() => onGoToClause(risk.clause_id as string)}
            >
              Go to clause
              <ArrowUpRight className="h-3.5 w-3.5" aria-hidden />
            </Button>
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">Document-wide finding — not tied to a single clause.</p>
        )}
      </CardHeader>

      <CardContent className="min-h-0 flex-1 space-y-5 overflow-y-auto">
        {highSeverity ? (
          <Alert variant="warning">
            <AlertTitle className="flex items-center gap-1.5">
              <ShieldAlert className="h-4 w-4" aria-hidden />
              Human review required
            </AlertTitle>
            <AlertDescription>
              This is a {severity}-severity finding. Have a qualified professional review the clause and the
              recommended action before signing or relying on this contract.
            </AlertDescription>
          </Alert>
        ) : null}

        <section className="space-y-1.5">
          <FieldLabel>What it says</FieldLabel>
          <p className="text-sm leading-relaxed">{risk.explanation}</p>
        </section>

        <section className="space-y-1.5">
          <FieldLabel icon={<Quote className="h-3.5 w-3.5" aria-hidden />}>Exact supporting evidence</FieldLabel>
          {evidenceUnbound ? (
            <p className="border border-dashed border-border p-3 text-sm text-muted-foreground">
              Supporting evidence is not directly bound to a passage.
              {risk.search_scope ? (
                <span className="mt-1 block text-xs">{risk.search_scope}</span>
              ) : null}
            </p>
          ) : evidenceSpans.length > 0 ? (
            <ul className="space-y-2.5">
              {evidenceSpans.map((span, i) => (
                <li key={i} className="border-l-2 border-primary/50 pl-3">
                  <blockquote className="font-mono text-[13px] leading-[1.7] text-foreground/90">
                    “{span.text}”
                  </blockquote>
                  <p className="mt-1.5 font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                    {span.role}
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="border border-dashed border-border p-3 text-sm text-muted-foreground">
              No quoted evidence was captured for this finding.
            </p>
          )}
        </section>

        <section className="space-y-1.5">
          <FieldLabel icon={<Info className="h-3.5 w-3.5" aria-hidden />}>Why it matters</FieldLabel>
          <p className="text-sm leading-relaxed">
            {risk.impact_summary ?? 'Not available in analysis.'}
          </p>
        </section>

        {risk.affected_parties?.length ? (
          <section className="space-y-1.5">
            <FieldLabel icon={<Users className="h-3.5 w-3.5" aria-hidden />}>Who is affected</FieldLabel>
            <p className="text-sm leading-relaxed">{risk.affected_parties.join(', ')}</p>
          </section>
        ) : null}

        <section className="space-y-1.5">
          <FieldLabel icon={<Target className="h-3.5 w-3.5" aria-hidden />}>Suggested review action</FieldLabel>
          <p className="text-sm leading-relaxed">
            {risk.review_action ?? risk.recommendation ?? 'Not available in analysis.'}
          </p>
        </section>

        {risk.uncertainty_note ? (
          <section className="space-y-1.5">
            <FieldLabel>Uncertainty</FieldLabel>
            <p className="text-sm leading-relaxed text-muted-foreground">{risk.uncertainty_note}</p>
          </section>
        ) : null}

        {risk.related_clause_ids?.length ? (
          <section className="space-y-1.5">
            <FieldLabel>Related clauses</FieldLabel>
            <div className="flex flex-wrap gap-1.5">
              {risk.related_clause_ids.map((cid) => (
                <button
                  key={cid}
                  type="button"
                  onClick={() => onGoToClause(cid)}
                  className="border border-border px-2.5 py-1 font-mono text-xs text-muted-foreground transition-colors hover:border-primary hover:text-primary"
                  title={cid}
                >
                  {cid.slice(-8)}
                </button>
              ))}
            </div>
            {risk.cross_reference_note ? (
              <p className="mt-1.5 text-xs text-muted-foreground">{risk.cross_reference_note}</p>
            ) : null}
          </section>
        ) : null}

        {risk.case_law?.length ? (
          <section className="space-y-2">
            <FieldLabel icon={<Gavel className="h-3.5 w-3.5" aria-hidden />}>Legal references</FieldLabel>
            <ul className="space-y-3">
              {risk.case_law.map((c) => (
                <CaseLawEntry key={c.citation} entry={c} />
              ))}
            </ul>
          </section>
        ) : null}

        <section className="space-y-1.5">
          <FieldLabel>Confidence / uncertainty</FieldLabel>
          <p className="text-sm text-muted-foreground">
            No calibrated confidence provided. This finding came from a{' '}
            {risk.source === 'model' ? 'machine-learning' : 'rule-based'} pass with a{' '}
            {risk.evidence_status} evidence status.
          </p>
        </section>
      </CardContent>
    </Card>
  );
}
