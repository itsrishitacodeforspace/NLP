import type { ReactNode } from 'react';
import type { EvidenceSpan, RiskFlag } from '@/types';
import { SEVERITY_META, toSeverity } from '@/lib/severity';
import { cn } from '@/lib/utils';

export interface ClauseSpan {
  span: EvidenceSpan;
  risk: RiskFlag;
  selected: boolean;
}

/**
 * Build the clause's children, wrapping each evidence span's exact substring
 * (offsets are into `clauseText`) in a severity-colored, clickable span.
 * No span => no highlight: callers render a clause-level indicator instead.
 * Offsets are clamped to the clause text so a drifted span never corrupts
 * the rendering.
 */
export function renderClauseWithHighlights(
  clauseText: string,
  spans: ClauseSpan[],
  onSelectRisk: (riskId: string) => void
): ReactNode[] {
  if (spans.length === 0) return [clauseText];

  interface Point {
    pos: number;
    end: number;
    risk: RiskFlag;
    selected: boolean;
  }
  const points: Point[] = [];
  for (const { span, risk, selected } of spans) {
    const start = Math.max(0, Math.min(span.char_start, clauseText.length));
    const end = Math.max(start, Math.min(span.char_end, clauseText.length));
    if (end > start) points.push({ pos: start, end, risk, selected });
  }

  if (points.length === 0) return [clauseText];

  points.sort((a, b) => a.pos - b.pos);
  const children: ReactNode[] = [];
  let lastEnd = 0;
  const flush = (to: number) => {
    if (to > lastEnd) children.push(clauseText.slice(lastEnd, to));
  };

  for (const p of points) {
    if (p.pos < lastEnd) continue; // overlapping spans: keep the first one's coverage
    flush(p.pos);
    const meta = SEVERITY_META[toSeverity(p.risk.severity)];
    children.push(
      <span
        key={`${p.risk.risk_id}-${p.pos}`}
        role="button"
        tabIndex={0}
        data-risk-id={p.risk.risk_id}
        title={p.risk.name}
        aria-label={`Finding: ${p.risk.name}`}
        onClick={() => onSelectRisk(p.risk.risk_id)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onSelectRisk(p.risk.risk_id);
          }
        }}
        className={cn(
          'cursor-pointer rounded-sm border-l-2 px-0.5 text-inherit transition-opacity',
          meta.bg,
          meta.border,
          p.selected
            ? 'ring-2 ring-ring ring-offset-1 ring-offset-card'
            : 'hover:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'
        )}
      >
        {clauseText.slice(p.pos, p.end)}
      </span>
    );
    lastEnd = p.end;
  }
  flush(clauseText.length);
  return children;
}
