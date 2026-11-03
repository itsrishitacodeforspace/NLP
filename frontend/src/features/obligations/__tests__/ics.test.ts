import { describe, expect, it } from 'vitest';
import { buildIcs, shouldIncludeInIcs } from '@/features/obligations/ics';
import type { Obligation } from '@/types';

const base: Obligation = {
  obligation_id: 'ob-1',
  clause_id: 'cl-1',
  text: 'Pay all amounts within 30 days of invoice',
  obligation_type: 'obligation',
  subject: 'Customer',
  counterparty: 'Provider',
  action: 'pay',
  object: 'all amounts',
  condition: null,
  deadline_expression: '30 days',
  deadline_date: '2026-12-01',
  frequency: null,
  risk_level: 'medium',
  confidence: 0.8,
  source: 'rule',
  char_start: null,
  char_end: null,
};

describe('features/obligations/ics.ts — shouldIncludeInIcs', () => {
  it('includes obligations with a definite deadline_date', () => {
    expect(shouldIncludeInIcs(base)).toBe(true);
  });

  it('excludes obligations without a deadline_date', () => {
    expect(shouldIncludeInIcs({ ...base, deadline_date: null })).toBe(false);
    expect(shouldIncludeInIcs({ ...base, deadline_date: undefined })).toBe(false);
    expect(shouldIncludeInIcs({ ...base, deadline_date: '   ' })).toBe(false);
  });

  it('excludes unparseable deadline dates', () => {
    expect(shouldIncludeInIcs({ ...base, deadline_date: 'whenever' })).toBe(false);
  });

  it('excludes conditional obligations (no fixed action date)', () => {
    expect(shouldIncludeInIcs({ ...base, obligation_type: 'condition' })).toBe(false);
    expect(shouldIncludeInIcs({ ...base, obligation_type: 'right' })).toBe(false);
    expect(shouldIncludeInIcs({ ...base, obligation_type: 'prohibition' })).toBe(false);
  });
});

describe('features/obligations/ics.ts — buildIcs', () => {
  it('produces a well-formed VCALENDAR wrapper with no events when empty', () => {
    const ics = buildIcs([]);
    expect(ics).toContain('BEGIN:VCALENDAR');
    expect(ics).toContain('END:VCALENDAR');
    expect(ics).toContain('VERSION:2.0');
    expect(ics).not.toContain('BEGIN:VEVENT');
  });

  it('produces a well-formed VCALENDAR when there are events', () => {
    const ics = buildIcs([base]);
    expect(ics).toContain('BEGIN:VCALENDAR');
    expect(ics).toContain('END:VCALENDAR');
    expect(ics).toContain('VERSION:2.0');
    expect(ics).toContain('BEGIN:VEVENT');
  });

  it('emits an all-day VEVENT for each included obligation', () => {
    const ics = buildIcs([base]);
    expect(ics).toContain('BEGIN:VEVENT');
    expect(ics).toContain('DTSTART;VALUE=DATE:20261201');
    // All-day events use the exclusive end date (start + 1 day).
    expect(ics).toContain('DTEND;VALUE=DATE:20261202');
    expect(ics).toContain('UID:ob-1@bharatcontract');
    expect(ics).toContain('SUMMARY:Obligation: Pay all amounts within 30 days of invoice');
    expect(ics).toContain('END:VEVENT');
  });

  it('excludes obligations without definite dates or conditionals', () => {
    const ics = buildIcs([
      base,
      { ...base, obligation_id: 'ob-2', deadline_date: null },
      { ...base, obligation_id: 'ob-3', obligation_type: 'condition' },
    ]);
    expect(ics).toContain('UID:ob-1@bharatcontract');
    expect(ics).not.toContain('ob-2');
    expect(ics).not.toContain('ob-3');
  });

  it('escapes RFC 5545 special characters in summary/description', () => {
    const ics = buildIcs([{ ...base, text: 'Pay 50%; notify, promptly' }]);
    // RFC 5545 does NOT require escaping '%' — only \ ; , and newlines are.
    expect(ics).toContain('SUMMARY:Obligation: Pay 50%\\; notify\\, promptly');
  });
});
