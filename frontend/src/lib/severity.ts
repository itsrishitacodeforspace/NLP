import type { RiskSeverity } from '@/types';

export type Severity = RiskSeverity | 'informational';

/** Canonical ordering, most severe first. */
export const SEVERITY_ORDER: Severity[] = [
  'critical',
  'high',
  'medium',
  'low',
  'informational',
];

export interface SeverityMeta {
  label: string;
  /** Tailwind text color class. */
  text: string;
  /** Tailwind bg tint class (subtle). */
  bg: string;
  /** Tailwind border class. */
  border: string;
  /** Solid hex for charts (recharts). */
  hex: string;
}

export const SEVERITY_META: Record<Severity, SeverityMeta> = {
  critical: {
    label: 'Critical',
    text: 'text-risk-critical',
    bg: 'bg-risk-critical/10',
    border: 'border-risk-critical/40',
    hex: '#dc2626',
  },
  high: {
    label: 'High',
    text: 'text-risk-high',
    bg: 'bg-risk-high/10',
    border: 'border-risk-high/40',
    hex: '#ea580c',
  },
  medium: {
    label: 'Medium',
    text: 'text-risk-medium',
    bg: 'bg-risk-medium/10',
    border: 'border-risk-medium/40',
    hex: '#d97706',
  },
  low: {
    label: 'Low',
    text: 'text-risk-low',
    bg: 'bg-risk-low/10',
    border: 'border-risk-low/40',
    hex: '#16a34a',
  },
  informational: {
    label: 'Informational',
    text: 'text-muted-foreground',
    bg: 'bg-muted/40',
    border: 'border-border',
    hex: '#64748b',
  },
};

export function severityRank(s: string): number {
  const i = SEVERITY_ORDER.indexOf(s as Severity);
  return i === -1 ? SEVERITY_ORDER.length : i;
}

/** Coerce a backend severity (or unknown) into a display severity. */
export function toSeverity(value: string | null | undefined): Severity {
  if (value && value in SEVERITY_META) return value as Severity;
  return 'informational';
}

export function severityMeta(s: string | null | undefined): SeverityMeta {
  return SEVERITY_META[toSeverity(s)];
}
