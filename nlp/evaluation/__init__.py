"""Deterministic, reproducible evaluation harness over a small labelled synthetic corpus."""
from __future__ import annotations

from nlp.evaluation.cases import CASES, EvalCase, ObligationExpectation
from nlp.evaluation.harness import (
    CaseResult,
    EvaluationReport,
    InvariantResult,
    run_all,
    run_case,
)

__all__ = [
    "CASES",
    "EvalCase",
    "ObligationExpectation",
    "CaseResult",
    "EvaluationReport",
    "InvariantResult",
    "run_all",
    "run_case",
]
