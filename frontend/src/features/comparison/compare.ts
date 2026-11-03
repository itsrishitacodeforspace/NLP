'use client';

import { diffLines, diffChars } from 'diff';
import type { Clause, Obligation, RiskFlag } from '@/types';

/**
 * Frontend-only comparison of two contracts' stored analysis.
 * The backend has NO comparison endpoint — everything here runs in the browser
 * over the four standard endpoints (summary/clauses/obligations/risks).
 */

export type ChangeKind = 'added' | 'removed' | 'modified' | 'unchanged';

export interface ClauseMatch {
  a: Clause | null;
  b: Clause | null;
  kind: ChangeKind;
  /** How the pair was matched, surfaced in the UI for honesty. */
  matchBasis: 'section_number' | 'heading' | 'ordinal' | 'single';
}

/**
 * Match clauses A→B.
 * Order of preference: section_number, then normalized heading, then ordinal
 * position. Unmatched remainder on either side becomes added/removed.
 */
export function matchClauses(a: Clause[], b: Clause[]): ClauseMatch[] {
  const norm = (s: string | null | undefined) => (s ?? '').trim().toLowerCase().replace(/\s+/g, ' ');

  const usedB = new Set<number>();
  const matches: ClauseMatch[] = [];
  const unmatchedA: { clause: Clause; idx: number }[] = [];

  // 1) section_number
  const bySection = new Map<string, number>();
  b.forEach((c, i) => {
    const key = norm(c.section_number);
    if (key && !bySection.has(key)) bySection.set(key, i);
  });
  a.forEach((c, i) => {
    const key = norm(c.section_number);
    if (key) {
      const bi = bySection.get(key);
      if (bi !== undefined && !usedB.has(bi)) {
        usedB.add(bi);
        matches.push(makeMatch(c, b[bi], 'section_number'));
        return;
      }
    }
    unmatchedA.push({ clause: c, idx: i });
  });

  // 2) heading (only when both have one)
  const byHeading = new Map<string, number>();
  b.forEach((c, i) => {
    const key = norm(c.heading);
    if (key && !byHeading.has(key)) byHeading.set(key, i);
  });
  const stillUnmatched: { clause: Clause; idx: number }[] = [];
  for (const { clause, idx } of unmatchedA) {
    const key = norm(clause.heading);
    if (key) {
      const bi = byHeading.get(key);
      if (bi !== undefined && !usedB.has(bi)) {
        usedB.add(bi);
        matches.push(makeMatch(clause, b[bi], 'heading'));
        continue;
      }
    }
    stillUnmatched.push({ clause, idx });
  }

  // 3) ordinal position (fallback)
  const freeB = b.map((_, i) => i).filter((i) => !usedB.has(i));
  const freeA = stillUnmatched.map(({ clause, idx }) => ({ clause, idx }));
  const n = Math.min(freeA.length, freeB.length);
  for (let i = 0; i < n; i++) {
    usedB.add(freeB[i]);
    matches.push(makeMatch(freeA[i].clause, b[freeB[i]], 'ordinal'));
  }
  const leftoverA = freeA.slice(n);
  const leftoverB = freeB.slice(n);

  for (const { clause } of leftoverA) matches.push(makeMatch(clause, null, 'single'));
  for (const bi of leftoverB) matches.push(makeMatch(null, b[bi], 'single'));

  // Sort: by A ordinal, added items keep their B position at the end.
  return matches;
}

function makeMatch(a: Clause | null, b: Clause | null, matchBasis: ClauseMatch['matchBasis']): ClauseMatch {
  let kind: ChangeKind;
  if (a && b) {
    const same = (a.text ?? '').trim() === (b.text ?? '').trim();
    kind = same ? 'unchanged' : 'modified';
  } else if (a) kind = 'removed';
  else kind = 'added';
  return { a, b, kind, matchBasis };
}

/** One diff segment as rendered by jsdiff's diffLines (line-granularity). */
export interface DiffSegment {
  value: string;
  added: boolean;
  removed: boolean;
}

export function textDiff(aText: string, bText: string): DiffSegment[] {
  const parts = diffLines(aText, bText);
  // diffLines splits on \n; a contract clause is usually a single line, in which
  // case the whole text is one changed segment. Split it down to word granularity
  // so the highlighting stays readable.
  if (parts.length <= 2) {
    return diffChars(aText, bText).map((p) => ({ value: p.value, added: !!p.added, removed: !!p.removed }));
  }
  return parts.map((p) => ({ value: p.value, added: !!p.added, removed: !!p.removed }));
}

export interface RiskDiff {
  ruleId: string;
  clauseId: string | null;
  name: string;
  a?: RiskFlag;
  b?: RiskFlag;
  /** 'removed' = in A only, 'new' = in B only, 'severity' = in both, different severity. */
  status: 'removed' | 'new' | 'severity';
}

/** Risks matched by rule_id + clause_id. */
export function diffRisks(a: RiskFlag[], b: RiskFlag[]): { removed: RiskFlag[]; added: RiskFlag[]; severityChanges: RiskDiff[] } {
  const key = (r: RiskFlag) => `${r.rule_id}::${r.clause_id ?? ''}`;
  const mapA = new Map<string, RiskFlag>();
  const mapB = new Map<string, RiskFlag>();
  a.forEach((r) => mapA.set(key(r), r));
  b.forEach((r) => mapB.set(key(r), r));

  const removed: RiskFlag[] = [];
  const added: RiskFlag[] = [];
  const severityChanges: RiskDiff[] = [];

  for (const [k, ra] of mapA) {
    const rb = mapB.get(k);
    if (!rb) removed.push(ra);
    else if (ra.severity !== rb.severity) {
      severityChanges.push({ ruleId: ra.rule_id, clauseId: ra.clause_id ?? null, name: ra.name, a: ra, b: rb, status: 'severity' });
    }
  }
  for (const [k, rb] of mapB) if (!mapA.has(k)) added.push(rb);

  return { removed, added, severityChanges };
}

export interface ObligationDiff {
  added: Obligation[];
  removed: Obligation[];
  countA: number;
  countB: number;
}

/**
 * Obligations matched by obligation_id first, then by (subject, action, object)
 * — the backend's ids embed the clause ordinal, so id-matching is usually enough
 * only within the same contract.
 */
export function diffObligations(a: Obligation[], b: Obligation[]): ObligationDiff {
  const sig = (o: Obligation) =>
    [o.subject ?? '', o.action ?? '', o.object ?? '', o.obligation_type].map((s) => (s ?? '').trim().toLowerCase()).join('::');
  const idsB = new Set(b.map((o) => o.obligation_id));
  const removed = a.filter((o) => !idsB.has(o.obligation_id) && !b.some((x) => sig(x) === sig(o)));
  const sigsRemoved = new Set(removed.map(sig));
  const added = b.filter((o) => !a.some((x) => x.obligation_id === o.obligation_id || sigsRemoved.has(sig(o))));
  return { added, removed, countA: a.length, countB: b.length };
}

export interface Conflict {
  clause: ClauseMatch;
  aRisk: RiskFlag;
  bRisk: RiskFlag;
}

/**
 * Conservative "possible conflict" flag: a matched clause whose TEXT changed and
 * which carries a risk in A AND a *different* risk in B. Labeled as needing
 * review — never asserted as a real legal conflict.
 */
export function findPossibleConflicts(matches: ClauseMatch[], risksA: RiskFlag[], risksB: RiskFlag[]): Conflict[] {
  const risksFor = (risks: RiskFlag[], clauseId: string | null | undefined) =>
    risks.filter((r) => (r.clause_id ?? null) === (clauseId ?? null));

  const out: Conflict[] = [];
  for (const m of matches) {
    if (m.kind !== 'modified' || !m.a || !m.b) continue;
    const ra = risksFor(risksA, m.a.clause_id);
    const rb = risksFor(risksB, m.b.clause_id);
    if (ra.length === 0 || rb.length === 0) continue;
    // Only flag when the risk sets differ (a new / different risk after the edit).
    const sameSet =
      ra.length === rb.length &&
      ra.every((x) => rb.some((y) => y.rule_id === x.rule_id && y.severity === x.severity));
    if (sameSet) continue;
    out.push({ clause: m, aRisk: ra[0], bRisk: rb[0] });
  }
  return out;
}
