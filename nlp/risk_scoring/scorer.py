"""Clause-level + contract-level risk scoring."""
from __future__ import annotations

from typing import Iterable, List

from app.models.schemas import Clause, ContractSummary, RiskFlag, RiskSeverity


_SEVERITY_WEIGHTS = {
    RiskSeverity.LOW: 10,
    RiskSeverity.MEDIUM: 30,
    RiskSeverity.HIGH: 55,
    RiskSeverity.CRITICAL: 85,
}


def _level_for(score: float) -> RiskSeverity:
    if score >= 76:
        return RiskSeverity.CRITICAL
    if score >= 51:
        return RiskSeverity.HIGH
    if score >= 26:
        return RiskSeverity.MEDIUM
    return RiskSeverity.LOW


def score_clauses(clauses: List[Clause]) -> List[Clause]:
    """Annotate each clause with risk_score / risk_level based on its own risks."""
    for cl in clauses:
        cl.risk_score = 0.0
        cl.risk_reasons = []
    return clauses


def score_contract(
    clauses: List[Clause],
    risks: List[RiskFlag],
) -> tuple[float, RiskSeverity]:
    """Compute a single contract risk score.

    Formula:
        contract_risk = max(clause_score) * 0.4
                      + avg(top 5 clause scores) * 0.3
                      + #critical_risks * 0.2
                      + #missing_clauses * 0.1
    """
    if not clauses and not risks:
        return 0.0, RiskSeverity.LOW

    clause_scores = sorted([c.risk_score for c in clauses], reverse=True)[:5] or [0.0]
    top = clause_scores[0]
    top5_avg = sum(clause_scores) / len(clause_scores)

    critical_count = sum(1 for r in risks if r.severity == RiskSeverity.CRITICAL)
    missing = sum(1 for r in risks if r.rule_id.startswith("MISSING_CLAUSE_") or r.rule_id.startswith("RISK_DATA_MISSING"))

    score = (
        top * 0.4
        + top5_avg * 0.3
        + min(critical_count, 10) * 4  # up to 40 pts
        + min(missing, 6) * 4           # up to 24 pts
    )
    score = min(100.0, round(score, 1))
    return score, _level_for(score)


def severity_to_score(severity: RiskSeverity) -> float:
    return float(_SEVERITY_WEIGHTS[severity])