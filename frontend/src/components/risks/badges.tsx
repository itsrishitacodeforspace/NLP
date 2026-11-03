'use client';

import * as React from 'react';
import { cn } from '@/lib/utils';
import { severityMeta, toSeverity, type Severity } from '@/lib/severity';

export function SeverityBadge({ severity, className }: { severity: string; className?: string }) {
  const meta = severityMeta(severity);
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium',
        meta.bg,
        meta.text,
        meta.border,
        className
      )}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden />
      {meta.label}
    </span>
  );
}

/** Source badge: rule-based vs ML/model, with an honest "unverified" cue. */
export function SourceBadge({ source, evidenceStatus }: { source?: string; evidenceStatus?: string }) {
  const isModel = source === 'model';
  const unverified = evidenceStatus === 'unverified' || evidenceStatus === 'unavailable' || evidenceStatus === 'contextual';
  return (
    <span
      className={cn(
        'inline-flex items-center rounded border px-1.5 py-0.5 text-[11px] font-medium',
        isModel
          ? 'border-primary/30 bg-primary/10 text-primary'
          : 'border-border bg-muted/50 text-muted-foreground'
      )}
      title={isModel ? 'Model-supported finding (review recommended)' : 'Rule-based finding'}
    >
      {isModel ? 'ML' : 'Rule'}
      {unverified ? ' · unverified' : ''}
    </span>
  );
}

/** Overall risk gauge (0–100). Uses the real backend score only. */
export function RiskGauge({ score, level, caveat }: { score: number; level: string; caveat?: string }) {
  const sev: Severity = toSeverity(level);
  const meta = severityMeta(sev);
  const r = 42;
  const circ = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, score)) / 100;
  return (
    <div className="flex items-center gap-4">
      <svg width="110" height="110" viewBox="0 0 110 110" role="img" aria-label={`Risk score ${score} of 100, ${meta.label}`}>
        <circle cx="55" cy="55" r={r} fill="none" stroke="currentColor" className="text-muted" strokeWidth="10" />
        <circle
          cx="55"
          cy="55"
          r={r}
          fill="none"
          stroke={meta.hex}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={circ}
          strokeDashoffset={circ * (1 - pct)}
          transform="rotate(-90 55 55)"
        />
        <text x="55" y="52" textAnchor="middle" className="fill-foreground text-2xl font-semibold">
          {Math.round(score)}
        </text>
        <text x="55" y="70" textAnchor="middle" className="fill-muted-foreground text-[10px] uppercase tracking-wide">
          {meta.label}
        </text>
      </svg>
      {caveat ? <p className="max-w-[220px] text-xs text-muted-foreground">{caveat}</p> : null}
    </div>
  );
}
