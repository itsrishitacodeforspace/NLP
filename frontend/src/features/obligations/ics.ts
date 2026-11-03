/**
 * ICS (iCalendar) export of obligations.
 *
 * Pure function — no DOM/network. Only obligations with a definite
 * `deadline_date` and an unconditional `obligation_type` are exported
 * (see shouldIncludeInIcs). Each becomes an all-day VEVENT.
 */
import type { Obligation } from '@/types';

/**
 * An obligation is ICS-exportable only when:
 *  - it has a concrete `deadline_date` (a resolvable ISO/`YYYY-MM-DD` date), and
 *  - it is an unconditional obligation (type 'obligation').
 *
 * Rights/prohibitions are not calendar actions; conditions have no fixed date.
 */
export function shouldIncludeInIcs(o: Obligation): boolean {
  if (!o.deadline_date || !o.deadline_date.trim()) return false;
  if (o.obligation_type && o.obligation_type !== 'obligation') return false;
  return !Number.isNaN(new Date(o.deadline_date).getTime());
}

/** Build an iCalendar document (all-day VEVENTs) from the given obligations. */
export function buildIcs(obligations: Obligation[], calendarTitle = 'BharatContract obligations'): string {
  const included = obligations.filter(shouldIncludeInIcs);

  const lines: string[] = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//BharatContract AI//Obligations 1.0//EN',
    `CALSCALE:GREGORIAN`,
    `X-WR-CALNAME:${escapeText(calendarTitle)}`,
  ];

  for (const o of included) {
    const dt = icsDate(o.deadline_date as string);
    // All-day event: the ICS DATE range is exclusive-end, so end = dt + 1 day.
    const end = addDays(dt, 1);
    const uid = `${o.obligation_id}@bharatcontract`;
    lines.push(
      'BEGIN:VEVENT',
      `UID:${uid}`,
      `DTSTAMP:${dt}T000000Z`,
      `DTSTART;VALUE=DATE:${dt}`,
      `DTEND;VALUE=DATE:${end}`,
      `SUMMARY:${escapeText(`Obligation: ${o.text}`)}`,
      `DESCRIPTION:${escapeText(describeObligation(o))}`,
      'TRANSP:TRANSPARENT',
      'END:VEVENT'
    );
  }

  lines.push('END:VCALENDAR');
  // RFC 5545: CRLF line endings.
  return lines.join('\r\n') + '\r\n';
}

function describeObligation(o: Obligation): string {
  const parts = [
    `Type: ${o.obligation_type}`,
    o.subject ? `Subject: ${o.subject}` : null,
    o.counterparty ? `Counterparty: ${o.counterparty}` : null,
    o.deadline_expression ? `Deadline (as written): ${o.deadline_expression}` : null,
    o.frequency ? `Frequency: ${o.frequency}` : null,
    `Risk level: ${o.risk_level}`,
    `Confidence: ${Math.round((o.confidence ?? 0) * 100)}%`,
    `Source: ${o.source}`,
    `Clause: ${o.clause_id}`,
  ].filter(Boolean);
  return parts.join('\n');
}

/** Convert a date string to a YYYYMMDD value, using the UTC calendar day. */
function icsDate(value: string): string {
  const d = new Date(value);
  const y = d.getUTCFullYear();
  const m = String(d.getUTCMonth() + 1).padStart(2, '0');
  const day = String(d.getUTCDate()).padStart(2, '0');
  return `${y}${m}${day}`;
}

function addDays(yyyymmdd: string, days: number): string {
  const d = new Date(`${yyyymmdd.slice(0, 4)}-${yyyymmdd.slice(4, 6)}-${yyyymmdd.slice(6, 8)}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  const y = d.getUTCFullYear();
  const m = String(d.getUTCMonth() + 1).padStart(2, '0');
  const day = String(d.getUTCDate()).padStart(2, '0');
  return `${y}${m}${day}`;
}

/** Escape text per RFC 5545 §3.3.11. */
function escapeText(s: string): string {
  return s
    .replace(/\\/g, '\\\\')
    .replace(/\r\n|\n|\r/g, '\\n')
    .replace(/,/g, '\\,')
    .replace(/;/g, '\\;');
}
