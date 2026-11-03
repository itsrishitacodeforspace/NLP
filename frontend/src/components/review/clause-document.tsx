'use client';

import * as React from 'react';
import { FileText, Search } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';
import { SEVERITY_META, severityRank, toSeverity, type Severity } from '@/lib/severity';
import { useDebouncedValue } from '@/features/review/debounce';
import type { Clause, ContractSummary, EvidenceSpan, RiskFlag } from '@/types';
import { renderClauseWithHighlights } from '@/features/review/highlight';

interface ClauseDocumentProps {
  summary: ContractSummary;
  clauses: Clause[];
  risks: RiskFlag[];
  selectedRiskId: string | null;
  searchInput: string;
  onSearchInputChange: (value: string) => void;
  onSelectRisk: (riskId: string) => void;
  /** Register a clause DOM node so the page can scroll to a finding. */
  registerClauseEl: (clauseId: string, el: HTMLElement | null) => void;
}

/** Short, human label for a clause in the findings nav. */
function clauseLabel(clauses: Clause[], clauseId: string | null | undefined): string {
  if (!clauseId) return 'Document-wide';
  const c = clauses.find((x) => x.clause_id === clauseId);
  if (!c) return 'Unknown clause';
  if (c.heading) return c.heading;
  if (c.section_number) return `Section ${c.section_number}`;
  return `Clause ${clauses.indexOf(c) + 1}`;
}

export function ClauseDocument({
  summary,
  clauses,
  risks,
  selectedRiskId,
  searchInput,
  onSearchInputChange,
  onSelectRisk,
  registerClauseEl,
}: ClauseDocumentProps) {
  const search = useDebouncedValue(searchInput, 250);

  // Risks with evidence spans -> per-span highlights; without -> clause-level dots.
  const spansByClause = React.useMemo(() => {
    const map = new Map<string, { span: EvidenceSpan; risk: RiskFlag }[]>();
    for (const risk of risks) {
      if (!risk.clause_id) continue;
      for (const span of risk.evidence_spans ?? []) {
        const list = map.get(risk.clause_id) ?? [];
        list.push({ span, risk });
        map.set(risk.clause_id, list);
      }
    }
    return map;
  }, [risks]);

  const dotRisksByClause = React.useMemo(() => {
    const map = new Map<string, RiskFlag[]>();
    for (const risk of risks) {
      if (!risk.clause_id) continue;
      if ((spansByClause.get(risk.clause_id) ?? []).some((s) => s.risk.risk_id === risk.risk_id)) continue;
      const list = map.get(risk.clause_id) ?? [];
      list.push(risk);
      map.set(risk.clause_id, list);
    }
    return map;
  }, [risks, spansByClause]);

  const searchMatches = React.useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return null;
    const set = new Set<string>();
    for (const c of clauses) {
      if (c.text.toLowerCase().includes(q) || (c.heading ?? '').toLowerCase().includes(q)) {
        set.add(c.clause_id);
      }
    }
    return set;
  }, [clauses, search]);

  const visibleClauses = searchMatches ? clauses.filter((c) => searchMatches.has(c.clause_id)) : clauses;

  const groupedRisks = React.useMemo(() => {
    const groups = new Map<Severity, RiskFlag[]>();
    for (const risk of risks) {
      const key = toSeverity(risk.severity);
      const list = groups.get(key) ?? [];
      list.push(risk);
      groups.set(key, list);
    }
    return [...groups.entries()]
      .sort(([a], [b]) => severityRank(a) - severityRank(b))
      .map(([severity, list]) => ({
        severity,
        risks: [...list].sort(
          (a, b) => severityRank(a.severity) - severityRank(b.severity) || b.score - a.score
        ),
      }));
  }, [risks]);

  // Move the selection through the flat findings list with the arrow keys.
  const flatRiskIds = React.useMemo(
    () => groupedRisks.flatMap((g) => g.risks.map((r) => r.risk_id)),
    [groupedRisks]
  );
  const handleNavKeyDown = React.useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>) => {
      if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp' && e.key !== 'Home' && e.key !== 'End') return;
      e.preventDefault();
      if (flatRiskIds.length === 0) return;
      const idx = flatRiskIds.indexOf(selectedRiskId ?? '');
      let next: number;
      if (e.key === 'Home') next = 0;
      else if (e.key === 'End') next = flatRiskIds.length - 1;
      else if (e.key === 'ArrowDown') next = idx === -1 ? 0 : Math.min(flatRiskIds.length - 1, idx + 1);
      else next = idx <= 0 ? 0 : idx - 1;
      onSelectRisk(flatRiskIds[next]);
    },
    [flatRiskIds, selectedRiskId, onSelectRisk]
  );

  const meta = SEVERITY_META[toSeverity(summary.overall_risk_level)];

  return (
    <div className="flex h-full min-h-0 flex-col gap-4">
      <Card>
        <CardContent className="p-4 sm:p-5">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <FileText className="h-5 w-5 shrink-0 text-primary" aria-hidden />
            <div className="min-w-0 flex-1">
              <h1 className="truncate text-lg font-semibold leading-tight">{summary.title}</h1>
              <p className="truncate text-sm text-muted-foreground">
                {summary.parties?.length ? summary.parties.join(' · ') : 'Parties unknown'}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant="outline" className={cn(meta.text, 'gap-1.5')}>
                <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden />
                {meta.label}
              </Badge>
              <span className="text-sm text-muted-foreground" aria-label={`${summary.clause_count} clauses`}>
                {summary.clause_count} clauses
              </span>
            </div>
          </div>
          <div className="mt-3 grid grid-cols-1 gap-x-4 gap-y-1 text-xs text-muted-foreground sm:grid-cols-3">
            {summary.effective_date ? <span>Effective: {summary.effective_date}</span> : null}
            {summary.governing_law ? <span className="truncate">Law: {summary.governing_law}</span> : null}
            {summary.arbitration_seat ? (
              <span className="truncate">Arbitration seat: {summary.arbitration_seat}</span>
            ) : null}
            {summary.jurisdiction ? <span className="truncate">Jurisdiction: {summary.jurisdiction}</span> : null}
          </div>
          {summary.score_caveat ? (
            <p className="mt-3 text-xs italic text-muted-foreground">{summary.score_caveat}</p>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardContent className="flex flex-col gap-3 p-4 sm:p-5">
          <div className="flex flex-col gap-3 sm:flex-row">
            <div className="relative flex-1">
              <Search
                className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
                aria-hidden
              />
              <Input
                type="search"
                value={searchInput}
                onChange={(e) => onSearchInputChange(e.target.value)}
                placeholder="Search clauses…"
                aria-label="Search clauses"
                className="pl-8"
              />
            </div>
            <div
              role="listbox"
              aria-label="Findings, most severe first"
              tabIndex={0}
              onKeyDown={handleNavKeyDown}
              className="max-h-64 w-full overflow-y-auto rounded-md border p-1 outline-none focus-visible:ring-2 focus-visible:ring-ring sm:w-64"
            >
              <p className="px-2 py-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                Findings ({risks.length})
              </p>
              {risks.length === 0 ? (
                <p className="px-2 py-2 text-xs text-muted-foreground">No risk findings for this contract.</p>
              ) : null}
              {groupedRisks.map((group) => (
                <div key={group.severity}>
                  <p
                    className={cn(
                      'px-2 pb-0.5 pt-2 text-[11px] font-medium uppercase tracking-wide',
                      SEVERITY_META[group.severity].text
                    )}
                  >
                    {SEVERITY_META[group.severity].label}
                  </p>
                  {group.risks.map((risk) => (
                    <button
                      key={risk.risk_id}
                      type="button"
                      role="option"
                      aria-selected={risk.risk_id === selectedRiskId}
                      onClick={() => onSelectRisk(risk.risk_id)}
                      className={cn(
                        'flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left text-xs transition-colors',
                        risk.risk_id === selectedRiskId
                          ? 'bg-primary/10 text-primary'
                          : 'text-foreground hover:bg-accent hover:text-accent-foreground'
                      )}
                    >
                      <span
                        aria-hidden
                        className={cn(
                          'mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-current',
                          SEVERITY_META[toSeverity(risk.severity)].text
                        )}
                      />
                      <span className="min-w-0">
                        <span className="block truncate font-medium">{risk.name}</span>
                        <span className="block truncate text-muted-foreground">
                          {clauseLabel(clauses, risk.clause_id)}
                        </span>
                      </span>
                    </button>
                  ))}
                </div>
              ))}
            </div>
          </div>
          {searchMatches ? (
            <p className="text-xs text-muted-foreground" role="status">
              {searchMatches.size === 0
                ? `No clauses match “${search.trim()}”.`
                : `Showing ${searchMatches.size} of ${clauses.length} clauses matching “${search.trim()}”.`}
            </p>
          ) : null}
        </CardContent>
      </Card>

      <div className="min-h-72 flex-1 overflow-y-auto rounded-lg border bg-card" aria-label="Contract clauses">
        <Separator />
        <div className="space-y-4 p-4 sm:p-6">
          {visibleClauses.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">No clauses to display.</p>
          ) : null}
          {visibleClauses.map((clause) => {
            const spans = (spansByClause.get(clause.clause_id) ?? []).map((s) => ({
              span: s.span,
              risk: s.risk,
              selected: s.risk.risk_id === selectedRiskId,
            }));
            const dots = dotRisksByClause.get(clause.clause_id) ?? [];
            const isSelectedClause = spans.some((s) => s.selected);
            return (
              <section
                key={clause.clause_id}
                ref={(el) => registerClauseEl(clause.clause_id, el)}
                data-clause-id={clause.clause_id}
                className={cn(
                  'scroll-mt-24 rounded-lg border bg-card p-4 transition-shadow',
                  isSelectedClause ? 'border-border ring-2 ring-ring' : 'border-border'
                )}
              >
                <header className="flex flex-wrap items-center gap-2">
                  <h3 className="text-sm font-semibold">
                    {clause.section_number ? `${clause.section_number}. ` : ''}
                    {clause.heading ?? 'Clause'}
                  </h3>
                  {clause.page_hint ? (
                    <span className="text-[11px] text-muted-foreground">p. {clause.page_hint}</span>
                  ) : null}
                  {clause.clause_types?.length ? (
                    <span className="text-[11px] text-muted-foreground">· {clause.clause_types.join(', ')}</span>
                  ) : null}
                  {dots.length > 0 ? (
                    <span
                      className="ml-auto flex items-center gap-1"
                      title={dots.map((d) => d.name).join('; ')}
                    >
                      {dots.map((d) => (
                        <span
                          key={d.risk_id}
                          title={d.name}
                          aria-label={d.name}
                          className={cn(
                            'h-2 w-2 rounded-full bg-current',
                            SEVERITY_META[toSeverity(d.severity)].text,
                            d.risk_id === selectedRiskId && 'ring-2 ring-ring ring-offset-1 ring-offset-card'
                          )}
                        />
                      ))}
                    </span>
                  ) : null}
                </header>
                <p className="mt-2 whitespace-pre-line text-sm leading-relaxed">
                  {renderClauseWithHighlights(clause.text, spans, onSelectRisk)}
                </p>
              </section>
            );
          })}
        </div>
      </div>
    </div>
  );
}
