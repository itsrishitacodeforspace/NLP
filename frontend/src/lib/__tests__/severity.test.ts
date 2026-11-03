import { describe, expect, it } from 'vitest';
import { SEVERITY_META, SEVERITY_ORDER, severityMeta, severityRank, toSeverity } from '@/lib/severity';

describe('severity.ts', () => {
  describe('toSeverity', () => {
    it.each(['critical', 'high', 'medium', 'low'] as const)('maps valid severity %s to itself', (s) => {
      expect(toSeverity(s)).toBe(s);
    });

    it('passes through "informational"', () => {
      expect(toSeverity('informational')).toBe('informational');
    });

    it.each(['bogus', '', 'CRITICAL', 'Critical', null, undefined])(
      'coerces unknown value %p to "informational"',
      (v) => {
        expect(toSeverity(v)).toBe('informational');
      }
    );
  });

  describe('SEVERITY_ORDER / severityRank', () => {
    it('orders critical > high > medium > low > informational', () => {
      expect(SEVERITY_ORDER).toEqual(['critical', 'high', 'medium', 'low', 'informational']);
    });

    it('ranks severities strictly by order', () => {
      expect(severityRank('critical')).toBe(0);
      expect(severityRank('high')).toBe(1);
      expect(severityRank('medium')).toBe(2);
      expect(severityRank('low')).toBe(3);
      expect(severityRank('informational')).toBe(4);
      expect(severityRank('critical')).toBeLessThan(severityRank('high'));
      expect(severityRank('high')).toBeLessThan(severityRank('medium'));
      expect(severityRank('medium')).toBeLessThan(severityRank('low'));
      expect(severityRank('low')).toBeLessThan(severityRank('informational'));
    });

    it('ranks unknown severities after all known ones', () => {
      expect(severityRank('nope')).toBe(SEVERITY_ORDER.length);
      expect(severityRank('nope')).toBeGreaterThan(severityRank('informational'));
    });
  });

  describe('severityMeta', () => {
    it('returns the canonical display label for each severity', () => {
      expect(severityMeta('critical').label).toBe('Critical');
      expect(severityMeta('high').label).toBe('High');
      expect(severityMeta('medium').label).toBe('Medium');
      expect(severityMeta('low').label).toBe('Low');
    });

    it('falls back to informational meta for unknown/empty input', () => {
      expect(severityMeta('whatever').label).toBe('Informational');
      expect(severityMeta(null).label).toBe('Informational');
      expect(severityMeta(undefined).label).toBe('Informational');
    });

    it('exposes tailwind classes and a hex for charts', () => {
      for (const s of Object.keys(SEVERITY_META)) {
        const meta = SEVERITY_META[s as keyof typeof SEVERITY_META];
        expect(meta.text).toMatch(/^text-/);
        expect(meta.bg).toMatch(/^bg-/);
        expect(meta.border).toMatch(/^border-/);
        expect(meta.hex).toMatch(/^#[0-9a-f]{6}$/i);
      }
    });
  });
});
