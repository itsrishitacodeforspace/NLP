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

# Metrics integration
from nlp.evaluation.metrics import (
    ClassificationMetrics,
    Entity,
    EvidenceMetrics,
    NERMetrics,
    ObligationMetrics,
    RiskMetrics,
    compute_classification_metrics,
    compute_evidence_metrics,
    compute_ner_metrics,
    compute_obligation_metrics,
    compute_risk_metrics,
)
from nlp.evaluation.metrics_integration import (
    CaseMetrics,
    IntegratedEvaluationReport,
    compute_case_metrics,
    extract_entities_from_analysis,
    extract_evidence_from_analysis,
    generate_integrated_report_json,
    load_gold_annotations,
    run_integrated_evaluation,
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
    # Metrics
    "ClassificationMetrics",
    "Entity",
    "EvidenceMetrics",
    "NERMetrics",
    "ObligationMetrics",
    "RiskMetrics",
    "compute_classification_metrics",
    "compute_evidence_metrics",
    "compute_ner_metrics",
    "compute_obligation_metrics",
    "compute_risk_metrics",
    # Integration
    "CaseMetrics",
    "IntegratedEvaluationReport",
    "compute_case_metrics",
    "extract_entities_from_analysis",
    "extract_evidence_from_analysis",
    "generate_integrated_report_json",
    "load_gold_annotations",
    "run_integrated_evaluation",
]
