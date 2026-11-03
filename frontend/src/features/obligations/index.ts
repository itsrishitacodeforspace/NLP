/**
 * Obligation status derivation and ICS export helpers.
 *
 * Honesty rules:
 * - Only obligations with a REAL `deadline_date` (definite, machine-parsed
 *   ISO date from the backend) get a date-derived status.
 * - Obligations with `deadline_date === null` are NEVER treated as having a
 *   date, even if `deadline_expression` text exists (e.g. "30 days").
 * - Statuses are exactly: Overdue, Upcoming, Scheduled, Recurring, No date,
 *   "No date (expression only)". Nothing else is invented.
 */
import type { Obligation } from '@/types';

export type ObligationStatus =
  | 'Overdue'
  | 'Upcoming'
  | 'Scheduled'
  | 'Recurring'
  | 'No date'
  | 'No date (expression only)';

const DAY_MS = 24 * 60 * 60 * 1000;

/** Parse a backend ISO date (date or datetime, possibly naive UTC). */
export function parseDeadlineDate(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  const d = new Date(iso.length === 10 ? iso + 'T00:00:00Z' : iso);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** Truncate to the start of today in local time. */
export function startOfToday(now: Date): Date {
  const d = new Date(now);
  d.setHours(0, 0, 0, 0);
  return d;
}

export interface DerivedStatus {
  status: ObligationStatus;
  /** Parsed deadline_date, if present. */
  date: Date | null;
}

/**
 * Derive the display status from REAL data only.
 *
 * Mapping (in precedence order):
 * 1. deadline_date present:
 *    - before today  → "Overdue"
 *    - within 30d    → "Upcoming"
 *    - further out   → "Scheduled"
 * 2. frequency present (no parseable date) → "Recurring"
 * 3. no date:
 *    - deadline_expression present → "No date (expression only)"
 *    - otherwise                   → "No date"
 */
export function deriveObligationStatus(o: Obligation, now: Date = new Date()): DerivedStatus {
  const date = parseDeadlineDate(o.deadline_date);
  if (date) {
    const today = startOfToday(now);
    if (date < today) return { status: 'Overdue', date };
    if (date.getTime() < today.getTime() + 31 * DAY_MS) return { status: 'Upcoming', date };
    return { status: 'Scheduled', date };
  }
  if (o.frequency) return { status: 'Recurring', date: null };
  if (o.deadline_expression) return { status: 'No date (expression only)', date: null };
  return { status: 'No date', date: null };
}

export const OBLIGATION_STATUS_STYLE: Record<ObligationStatus, string> = {
  Overdue: 'border-risk-critical/40 bg-risk-critical/10 text-risk-critical',
  Upcoming: 'border-risk-high/40 bg-risk-high/10 text-risk-high',
  Scheduled: 'border-border bg-muted/40 text-foreground',
  Recurring: 'border-primary/30 bg-primary/10 text-primary',
  'No date': 'border-border bg-muted/30 text-muted-foreground',
  'No date (expression only)': 'border-border bg-muted/30 text-muted-foreground',
};

/** Options for the deadline filter (client-side). */
export type DeadlineFilter = 'all' | 'has-date' | 'no-date' | 'overdue' | 'upcoming';

export function matchesDeadlineFilter(o: Obligation, filter: DeadlineFilter, now: Date = new Date()): boolean {
  if (filter === 'all') return true;
  const { status, date } = deriveObligationStatus(o, now);
  switch (filter) {
    case 'has-date':
      return date !== null;
    case 'no-date':
      return date === null;
    case 'overdue':
      return status === 'Overdue';
    case 'upcoming':
      return status === 'Upcoming';
    default:
      return true;
  }
}

/* ------------------------------------------------------------------ */
/* ICS export — ONLY obligations with a definite deadline_date         */
/* ------------------------------------------------------------------ */

function icsEscape(text: string): string {
  return text
    .replace(/\\/g, '\\\\')
    .replace(/\n/g, '\\n')
    .replace(/,/g, '\\,')
    .replace(/;/g, '\\;');
}

/** '2026-11-03T14:08:20' or '2026-11-03' → '20261103' */
function icsDate(iso: string): string {
  return iso.slice(0, 10).replace(/-/g, '');
}

/**
 * Build an .ics blob containing one VEVENT per obligation that has a
 * definite deadline_date. Conditional/uncertain dates (null deadline_date)
 * are EXCLUDED — only the backend-parsed, definite date is exported.
 */
export function buildObligationsIcs(obligations: Obligation[]): Blob {
  const dated = obligations.filter((o) => o.deadline_date && parseDeadlineDate(o.deadline_date) !== null);
  const lines: string[] = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//BharatContract//Obligation Tracker//EN',
    'CALSCALE:GREGORIAN',
    'METHOD:PUBLISH',
    'X-WR-CALNAME:Contractual deadlines',
  ];
  for (const o of dated) {
    const d = icsDate(o.deadline_date as string);
    const summary = [o.action, o.object].filter(Boolean).join(' ') || o.text;
    const descParts: string[] = [];
    descParts.push(`Responsible: ${o.subject ?? '—'} → ${o.counterparty ?? '—'}`);
    if (o.condition) descParts.push(`Condition: ${o.condition}`);
    descParts.push(`Source clause: ${o.clause_id}`);
    descParts.push('Contractual deadline extracted from the agreement — not a user reminder. Verify against the source text.');
    lines.push(
      'BEGIN:VEVENT',
      `UID:${o.obligation_id}`,
      // All-day local event on the deadline date (09:00–10:00 window).
      `DTSTART;TZID=LOCAL:${d}T090000`,
      `DTEND;TZID=LOCAL:${d}T100000`,
      `SUMMARY:${icsEscape(summary)}`,
      `DESCRIPTION:${icsEscape(descParts.join('\\n'))}`,
      'END:VEVENT'
    );
  }
  lines.push('END:VCALENDAR');
  return new Blob([lines.join('\r\n')], { type: 'text/calendar;charset=utf-8' });
}

/** True when at least one obligation carries a definite deadline_date. */
export function anyObligationHasDate(obligations: Obligation[]): boolean {
  return obligations.some((o) => parseDeadlineDate(o.deadline_date) !== null);
}
