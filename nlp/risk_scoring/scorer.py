"""Clause-level + contract-level risk scoring."""
from __future__ import annotations

from typing import List

from app.models.schemas import Clause, RiskFlag, RiskSeverity

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


def score_contract(
    clauses: List[Clause],
    risks: List[RiskFlag],
) -> tuple[float, RiskSeverity]:
    """Compute the contract score from the risk flags.

    Formula:
        highest flag score
        + 2 points per additional flag (max 20)
        + severity mass / 100 (max 10)
    capped at 100. This keeps a single critical finding in the critical band
    (>= 76) and prevents volume alone from inflating a low-risk contract.

    The score is an *ordinal risk heuristic*, not a calibrated probability: a
    higher value means more and/or more severe findings. 100 means "at the top
    of the critical band", not "100% certain" or "100% likely to be a problem".
    """
    if not risks:
        return 0.0, RiskSeverity.LOW

    top = max((r.score for r in risks), default=0.0)
    volume = min(20.0, max(0, len(risks) - 1) * 2.0)
    severity_mass = min(
        10.0,
        sum(severity_to_score(r.severity) for r in risks) / 100.0,
    )
    score = min(100.0, round(top + volume + severity_mass, 1))
    return score, _level_for(score)


def severity_to_score(severity: RiskSeverity) -> float:
    return float(_SEVERITY_WEIGHTS[severity])
