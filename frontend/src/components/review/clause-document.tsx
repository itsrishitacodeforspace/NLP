'use client';

import * as React from 'react';
import { Search } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { SeverityBadge } from '@/components/risks/badges';
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

  return (
    <div className="flex h-full min-h-0 flex-col gap-5">
      {/* Document masthead — editorial title block over a hairline rule. */}
      <header className="border-b border-border pb-4">
        <div className="flex flex-wrap items-start justify-between gap-x-5 gap-y-3">
          <div className="min-w-0">
            <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
              {summary.contract_type} · {summary.jurisdiction}
            </p>
            <h1 className="mt-1.5 font-display text-2xl font-semibold leading-[1.1] tracking-tight sm:text-3xl">
              {summary.title}
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              {summary.parties?.length ? summary.parties.join(' · ') : 'Parties unknown'}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span
              className="font-mono text-[11px] tracking-widest text-muted-foreground"
              aria-label={`${summary.clause_count} clauses`}
            >
              {summary.clause_count} clauses
            </span>
            <SeverityBadge severity={summary.overall_risk_level} />
          </div>
        </div>

        <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-1.5 font-mono text-[11px] sm:grid-cols-4">
          {[
            ['Effective', summary.effective_date],
            ['Law', summary.governing_law],
            ['Seat', summary.arbitration_seat],
            ['Jurisdiction', summary.jurisdiction],
          ]
            .filter(([, v]) => v)
            .map(([label, value]) => (
              <div key={label} className="min-w-0">
                <dt className="uppercase tracking-[0.12em] text-muted-foreground">{label}</dt>
                <dd className="truncate text-foreground" title={String(value)}>
                  {String(value)}
                </dd>
              </div>
            ))}
        </dl>

        {summary.score_caveat ? (
          <p className="mt-3 text-xs italic leading-relaxed text-muted-foreground">{summary.score_caveat}</p>
        ) : null}
      </header>

      {/* Toolbar — search + findings index, hairline separated. */}
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
          className="max-h-64 w-full overflow-y-auto border border-border bg-card p-1 outline-none focus-visible:ring-2 focus-visible:ring-ring sm:w-72"
        >
          <p className="px-2 py-1.5 font-mono text-[11px] uppercase tracking-[0.14em] text-muted-foreground">
            Findings ({risks.length})
          </p>
          {risks.length === 0 ? (
            <p className="px-2 py-2 text-xs text-muted-foreground">No risk findings for this contract.</p>
          ) : null}
          {groupedRisks.map((group) => (
            <div key={group.severity}>
              <p
                className={cn(
                  'px-2 pb-0.5 pt-2 font-mono text-[10px] uppercase tracking-[0.14em]',
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
                    'flex w-full items-start gap-2 border-l-2 px-2 py-1.5 text-left text-xs transition-colors',
                    risk.risk_id === selectedRiskId
                      ? 'border-primary bg-primary/10 text-foreground'
                      : 'border-transparent text-foreground hover:bg-accent'
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
        <p className="-mt-2 text-xs text-muted-foreground" role="status">
          {searchMatches.size === 0
            ? `No clauses match “${search.trim()}”.`
            : `Showing ${searchMatches.size} of ${clauses.length} clauses matching “${search.trim()}”.`}
        </p>
      ) : null}

      {/* The document — clauses as ruled sections, set in mono. */}
      <div
        className="min-h-72 flex-1 overflow-y-auto border border-border bg-card"
        aria-label="Contract clauses"
      >
        {visibleClauses.length === 0 ? (
          <p className="p-8 text-center text-sm text-muted-foreground">No clauses to display.</p>
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
                'scroll-mt-24 border-b border-border px-5 py-5 transition-colors last:border-b-0',
                isSelectedClause &&
                  'bg-primary/[0.05] shadow-[inset_3px_0_0_0_hsl(var(--primary))]'
              )}
            >
              <header className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                {clause.section_number ? (
                  <span aria-hidden className="font-mono text-[11px] tracking-[0.14em] text-primary">
                    §&nbsp;{clause.section_number}
                  </span>
                ) : null}
                <h3 className="font-display text-[15px] font-semibold leading-snug tracking-tight">
                  {clause.heading ?? 'Clause'}
                </h3>
                {clause.page_hint ? (
                  <span className="font-mono text-[10px] text-muted-foreground">p.&nbsp;{clause.page_hint}</span>
                ) : null}
                {clause.clause_types?.length ? (
                  <span className="font-mono text-[10px] text-muted-foreground">
                    · {clause.clause_types.join(', ')}
                  </span>
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
              <p className="mt-2.5 whitespace-pre-line font-mono text-[13px] leading-[1.75] text-foreground/90">
                {renderClauseWithHighlights(clause.text, spans, onSelectRisk)}
              </p>
            </section>
          );
        })}
      </div>
    </div>
  );
}
