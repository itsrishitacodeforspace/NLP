/**
 * Frontend-only risk grouping and compliance indicators.
 *
 * IMPORTANT: categories derived here are a *frontend* grouping of backend
 * `rule_id` prefixes for display purposes. They are NOT backend categories —
 * the backend ships `rule_id` (e.g. `RISK_LIABILITY_001`) and nothing else.
 */
import type { ContractSummary, RiskFlag, RiskSeverity } from '@/types';

/** Coarse display categories, derived from the `rule_id` prefix. */
export const RULE_CATEGORY_PREFIXES: Array<[prefix: string, label: string]> = [
  ['RISK_LIABILITY', 'Liability'],
  ['RISK_INDEMNITY', 'Indemnity'],
  ['RISK_DATA', 'Data protection'],
  ['RISK_TDS', 'TDS'],
  ['RISK_STAMP', 'Stamp duty'],
  ['RISK_TERM', 'Termination'],
  ['RISK_ARB', 'Arbitration'],
  ['RISK_GOV', 'Governing law'],
  ['RISK_RENEWAL', 'Renewal'],
  ['RISK_NONCOMPETE', 'Non-compete'],
  ['RISK_DISPUTE', 'Dispute'],
  ['S124', 'Indemnity (s.124)'],
  ['ML_RISK', 'Model'],
];

/** Map a backend `rule_id` to a coarse frontend category label. */
export function ruleIdToCategory(ruleId: string | null | undefined): string {
  if (!ruleId) return 'Other';
  for (const [prefix, label] of RULE_CATEGORY_PREFIXES) {
    if (ruleId.startsWith(prefix)) return label;
  }
  return 'Other';
}

const SEVERITIES: RiskSeverity[] = ['critical', 'high', 'medium', 'low'];

export interface CategorySeverityCell {
  category: string;
  counts: Record<RiskSeverity, number>;
  total: number;
}

/** Group risks by frontend category and severity. */
export function groupByCategorySeverities(risks: RiskFlag[]): CategorySeverityCell[] {
  const byCategory = new Map<string, Record<RiskSeverity, number>>();
  for (const risk of risks) {
    const cat = ruleIdToCategory(risk.rule_id);
    const sev = (SEVERITIES.includes(risk.severity) ? risk.severity : null) as RiskSeverity | null;
    if (!sev) continue;
    const counts = byCategory.get(cat) ?? { critical: 0, high: 0, medium: 0, low: 0 };
    counts[sev] += 1;
    byCategory.set(cat, counts);
  }
  return [...byCategory.entries()]
    .map(([category, counts]) => ({
      category,
      counts,
      total: counts.critical + counts.high + counts.medium + counts.low,
    }))
    .sort((a, b) => b.total - a.total || a.category.localeCompare(b.category));
}

export function countBySeverity(risks: RiskFlag[]): Record<RiskSeverity, number> {
  const counts: Record<RiskSeverity, number> = { critical: 0, high: 0, medium: 0, low: 0 };
  for (const risk of risks) {
    if (SEVERITIES.includes(risk.severity)) counts[risk.severity] += 1;
  }
  return counts;
}

/** Type-safe view of the backend `risk_score_breakdown` object. */
export interface ScoreBreakdownTerms {
  term: string;
  value: number;
}

export function scoreBreakdownTerms(
  breakdown: Record<string, unknown> | null | undefined
): ScoreBreakdownTerms[] {
  if (!breakdown) return [];
  const out: ScoreBreakdownTerms[] = [];
  for (const key of ['top', 'volume', 'severity_mass', 'cap_adjustment']) {
    const v = breakdown[key];
    if (typeof v === 'number' && Number.isFinite(v)) out.push({ term: key, value: v });
  }
  return out;
}

export function scoreBreakdownFindings(
  breakdown: Record<string, unknown> | null | undefined
): Record<RiskSeverity, number> {
  const out: Record<RiskSeverity, number> = { critical: 0, high: 0, medium: 0, low: 0 };
  const fbs = breakdown?.findings_by_severity;
  if (fbs && typeof fbs === 'object') {
    for (const [k, v] of Object.entries(fbs as Record<string, unknown>)) {
      if (SEVERITIES.includes(k as RiskSeverity) && typeof v === 'number') {
        out[k as RiskSeverity] = v;
      }
    }
  }
  return out;
}

/* ------------------------------------------------------------------ */
/* Compliance indicators (honesty rules: never imply "passed")        */
/* ------------------------------------------------------------------ */

export type ComplianceStatus =
  | 'Finding detected'
  | 'Review recommended'
  | 'Not detected'
  | 'Not evaluated'
  | 'Insufficient evidence';

export interface ComplianceIndicator {
  label: string;
  status: ComplianceStatus;
  /** Short evidence note shown on hover. */
  note: string;
}

/**
 * Neutral styling per status. Deliberately NO green "pass" state:
 * "Not detected" is slate (neutral), "Not evaluated" is gray.
 */
export const COMPLIANCE_STATUS_STYLE: Record<
  ComplianceStatus,
  { chip: string; text: string }
> = {
  'Finding detected': { chip: 'bg-risk-high/10 border-risk-high/30', text: 'text-risk-high' },
  'Review recommended': { chip: 'bg-risk-medium/10 border-risk-medium/30', text: 'text-risk-medium' },
  'Not detected': { chip: 'bg-slate-500/10 border-slate-400/30', text: 'text-slate-500' },
  'Not evaluated': { chip: 'bg-muted/40 border-border', text: 'text-muted-foreground' },
  'Insufficient evidence': { chip: 'bg-muted/40 border-border', text: 'text-muted-foreground' },
};

function hasRiskFor(risks: RiskFlag[], prefixes: string[]): RiskFlag | undefined {
  return risks.find((r) => prefixes.some((p) => r.rule_id.startsWith(p)));
}

function missingClauseMentioned(summary: ContractSummary, needles: string[]): string | null {
  const hay = (summary.missing_clauses ?? []).join(' \n').toLowerCase();
  const hit = needles.find((n) => hay.includes(n.toLowerCase()));
  return hit ?? null;
}

/**
 * Derive the compliance indicator grid from REAL backend signals only.
 *
 * Honesty rules:
 * - "Finding detected" — a matching risk exists.
 * - "Review recommended" — a related missing_clause, or a medium finding
 *   where the summary flags the topic as mentioned but risky.
 * - "Not detected" — no finding AND no missing-clause flag (neutral, NOT green).
 * - "Not evaluated" — the backend provides no signal for this category.
 * - "Insufficient evidence" — the backend explicitly marked the finding's
 *   evidence as insufficient/unverified (evidence_status-based).
 * There is intentionally NO "compliant/passed" state.
 */
export function buildComplianceIndicators(
  summary: ContractSummary,
  risks: RiskFlag[]
): ComplianceIndicator[] {
  const indicators: ComplianceIndicator[] = [];

  const push = (
    label: string,
    riskPrefixes: string[],
    options: {
      mentionedField?: keyof ContractSummary; // boolean mention flag
      missingNeedles?: string[];
      alwaysEvaluate?: boolean; // no boolean field exists — still "not detected" when nothing found
      valueField?: keyof ContractSummary; // e.g. governing_law / arbitration_seat
    } = {}
  ) => {
    const risk = hasRiskFor(risks, riskPrefixes);
    const missingHit = options.missingNeedles
      ? missingClauseMentioned(summary, options.missingNeedles)
      : null;

    if (risk) {
      const ev = risk.evidence_status;
      const insufficient = ev === 'insufficient' || ev === 'unavailable';
      indicators.push({
        label,
        status: insufficient ? 'Insufficient evidence' : 'Finding detected',
        note: `${risk.rule_id}: ${risk.name} (${risk.severity})`,
      });
      return;
    }
    if (missingHit) {
      indicators.push({
        label,
        status: 'Review recommended',
        note: `Missing clause flagged: ${missingHit}`,
      });
      return;
    }
    if (options.valueField) {
      const value = summary[options.valueField];
      if (typeof value === 'string' && value.length > 0) {
        indicators.push({
          label,
          status: 'Not detected',
          note: `Value present: ${value}`,
        });
        return;
      }
      indicators.push({ label, status: 'Not evaluated', note: 'No value detected in the contract.' });
      return;
    }
    if (options.mentionedField !== undefined) {
      const mentioned = summary[options.mentionedField] === true;
      indicators.push({
        label,
        status: 'Not detected',
        note: mentioned
          ? 'Topic mentioned in contract; no risk finding raised.'
          : 'Topic not detected in contract; no risk finding raised.',
      });
      return;
    }
    indicators.push({
      label,
      status: options.alwaysEvaluate ? 'Not detected' : 'Not evaluated',
      note: options.alwaysEvaluate
        ? 'No finding for this category.'
        : 'Backend provides no signal for this category.',
    });
  };

  push('Stamp duty', ['RISK_STAMP'], {
    mentionedField: 'stamp_duty_mentioned',
    missingNeedles: ['stamp duty', 'stamp-duty'],
  });
  push('Arbitration seat', ['RISK_ARB'], {
    valueField: 'arbitration_seat',
    missingNeedles: ['arbitration'],
  });
  push('Indemnity', ['RISK_INDEMNITY', 'S124'], {
    missingNeedles: ['indemn'],
  });
  push('TDS', ['RISK_TDS'], {
    mentionedField: 'tds_mentioned',
    missingNeedles: ['tds', 'tax deduction'],
  });
  push('GST', ['RISK_GST'], {
    mentionedField: 'gstin_mentioned',
    missingNeedles: ['gst'],
  });
  push('Governing law', ['RISK_GOV'], {
    valueField: 'governing_law',
    missingNeedles: ['governing law'],
  });
  push('Data protection', ['RISK_DATA'], {
    missingNeedles: ['data protection', 'confidential'],
  });
  push('Termination', ['RISK_TERM'], {
    missingNeedles: ['termination'],
  });
  push('Liability', ['RISK_LIABILITY'], {
    missingNeedles: ['liability'],
  });
  push('Confidentiality', ['RISK_CONFIDENTIALITY', 'RISK_CONF'], {
    missingNeedles: ['confidential'],
  });
  push('Intellectual property', ['RISK_IP', 'RISK_INTELLECTUAL'], {
    missingNeedles: ['intellectual property', 'ip '],
  });

  return indicators;
}
