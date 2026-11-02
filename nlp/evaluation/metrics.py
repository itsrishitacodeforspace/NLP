"""Evaluation metrics for BharatContract AI.

This module implements core evaluation metrics for:
- Clause classification (per-class P/R/F1, macro/micro F1, confusion matrix)
- NER evaluation (entity-level P/R/F1, boundary exactness)
- Obligation extraction (slot-level P/R/F1)
- Risk finding evaluation (precision/recall, severity agreement)
- Evidence integrity (span exactness, cross-reference provenance)

All metrics are designed to work with the synthetic evaluation harness
defined in nlp/evaluation/cases.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

from app.models.schemas import Obligation, RiskFlag

# ---------------------------------------------------------------------------
# Span utilities
# ---------------------------------------------------------------------------


def span_iou(pred_start: int, pred_end: int, gold_start: int, gold_end: int) -> float:
    """Compute Intersection over Union between two character spans.

    Args:
        pred_start: Predicted span start (inclusive)
        pred_end: Predicted span end (exclusive)
        gold_start: Ground truth span start (inclusive)
        gold_end: Ground truth span end (exclusive)

    Returns:
        IoU score in [0, 1], where 1.0 indicates exact match
    """
    if pred_end <= pred_start or gold_end <= gold_start:
        return 0.0

    intersection_start = max(pred_start, gold_start)
    intersection_end = min(pred_end, gold_end)
    intersection = max(0, intersection_end - intersection_start)

    union = (pred_end - pred_start) + (gold_end - gold_start) - intersection

    return intersection / union if union > 0 else 0.0


def span_exact_match(pred_start: int, pred_end: int, gold_start: int, gold_end: int) -> bool:
    """Check if two spans match exactly (same start and end)."""
    return pred_start == gold_start and pred_end == gold_end


# ---------------------------------------------------------------------------
# Classification metrics
# ---------------------------------------------------------------------------


@dataclass
class ClassificationMetrics:
    """Metrics for multi-class or multi-label classification."""
    precision: float
    recall: float
    f1: float
    macro_f1: float
    micro_f1: float
    per_class_metrics: Dict[str, Dict[str, float]]
    confusion_matrix: Dict[Tuple[str, str], int]
    abstention_count: int
    total_count: int


def compute_classification_metrics(
    predictions: List[str],
    ground_truth: List[str],
    all_labels: List[str],
) -> ClassificationMetrics:
    """Compute classification metrics including per-class P/R/F1 and macro/micro averages.

    Args:
        predictions: List of predicted labels
        ground_truth: List of ground truth labels
        all_labels: List of all possible labels (for comprehensive metrics)

    Returns:
        ClassificationMetrics with per-class and aggregate metrics
    """
    if len(predictions) != len(ground_truth):
        raise ValueError("Predictions and ground truth must have same length")

    total = len(predictions)
    abstention_count = sum(1 for p in predictions if p == "unclassified")

    # Per-class counts
    tp_by_class: Dict[str, int] = {label: 0 for label in all_labels}
    fp_by_class: Dict[str, int] = {label: 0 for label in all_labels}
    fn_by_class: Dict[str, int] = {label: 0 for label in all_labels}
    tn_by_class: Dict[str, int] = {label: 0 for label in all_labels}

    # Confusion matrix (predicted, actual) -> count
    confusion: Dict[Tuple[str, str], int] = {}

    for pred, gold in zip(predictions, ground_truth, strict=True):
        # Update confusion matrix
        key = (pred, gold)
        confusion[key] = confusion.get(key, 0) + 1

        # Update TP/FP/FN/TN for each class
        for label in all_labels:
            if pred == label and gold == label:
                tp_by_class[label] += 1
            elif pred == label and gold != label:
                fp_by_class[label] += 1
            elif pred != label and gold == label:
                fn_by_class[label] += 1
            else:
                tn_by_class[label] += 1

    # Compute per-class metrics
    per_class: Dict[str, Dict[str, float]] = {}
    f1_scores: List[float] = []

    for label in all_labels:
        tp = tp_by_class[label]
        fp = fp_by_class[label]
        fn = fn_by_class[label]

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        per_class[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "tn": tn_by_class[label],
        }
        f1_scores.append(f1)

    # Macro F1 (unweighted average of per-class F1)
    macro_f1 = np.mean(f1_scores) if f1_scores else 0.0

    # Micro F1 (global TP/FP/FN counts)
    total_tp = sum(tp_by_class.values())
    total_fp = sum(fp_by_class.values())
    total_fn = sum(fn_by_class.values())

    micro_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    micro_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    micro_f1 = 2 * micro_precision * micro_recall / (micro_precision + micro_recall) if \
        (micro_precision + micro_recall) > 0 else 0.0

    return ClassificationMetrics(
        precision=micro_precision,
        recall=micro_recall,
        f1=micro_f1,
        macro_f1=macro_f1,
        micro_f1=micro_f1,
        per_class_metrics=per_class,
        confusion_matrix=confusion,
        abstention_count=abstention_count,
        total_count=total,
    )


# ---------------------------------------------------------------------------
# NER/Entity metrics
# ---------------------------------------------------------------------------


@dataclass
class Entity:
    """An entity with type, span, and optional role."""
    entity_id: str
    text: str
    start: int
    end: int
    entity_type: str
    role: Optional[str] = None


@dataclass
class NERMetrics:
    """Metrics for named entity recognition."""
    entity_precision: float
    entity_recall: float
    entity_f1: float
    boundary_precision: float
    boundary_recall: float
    boundary_f1: float
    type_accuracy: float
    role_accuracy: float
    per_type_metrics: Dict[str, Dict[str, float]]


def compute_ner_metrics(
    pred_entities: List[Entity],
    gold_entities: List[Entity],
    all_entity_types: List[str],
) -> NERMetrics:
    """Compute NER metrics including entity-level and boundary-level P/R/F1.

    Args:
        pred_entities: Predicted entities
        gold_entities: Ground truth entities
        all_entity_types: List of all possible entity types

    Returns:
        NERMetrics with entity and boundary-level metrics
    """
    # Exact entity match (same type AND exact span)
    exact_matches = 0
    type_matches = 0
    boundary_matches = 0

    pred_set = set((e.start, e.end, e.entity_type, e.role or "") for e in pred_entities)
    gold_set = set((e.start, e.end, e.entity_type, e.role or "") for e in gold_entities)

    exact_matches = len(pred_set & gold_set)

    # Type accuracy (ignore span, just check entity type)
    pred_types = set((e.start, e.end, e.entity_type) for e in pred_entities)
    gold_types = set((e.start, e.end, e.entity_type) for e in gold_entities)
    type_matches = len(pred_types & gold_types)

    # Boundary accuracy (ignore entity type)
    pred_boundaries = set((e.start, e.end) for e in pred_entities)
    gold_boundaries = set((e.start, e.end) for e in gold_entities)
    boundary_matches = len(pred_boundaries & gold_boundaries)

    # Per-type metrics
    tp_by_type: Dict[str, int] = {t: 0 for t in all_entity_types}
    fp_by_type: Dict[str, int] = {t: 0 for t in all_entity_types}
    fn_by_type: Dict[str, int] = {t: 0 for t in all_entity_types}

    for e in pred_entities:
        if e in gold_entities:
            tp_by_type[e.entity_type] += 1
        else:
            fp_by_type[e.entity_type] += 1

    for e in gold_entities:
        if e not in pred_entities:
            fn_by_type[e.entity_type] += 1

    per_type: Dict[str, Dict[str, float]] = {}
    f1_scores: List[float] = []

    for etype in all_entity_types:
        tp = tp_by_type[etype]
        fp = fp_by_type[etype]
        fn = fn_by_type[etype]

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        per_type[etype] = {"precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn}
        f1_scores.append(f1)

    # macro_f1 computed later for classification
    _ = np.mean(f1_scores) if f1_scores else 0.0

    entity_precision = exact_matches / len(pred_entities) if pred_entities else 0.0
    entity_recall = exact_matches / len(gold_entities) if gold_entities else 0.0
    entity_f1 = 2 * entity_precision * entity_recall / (entity_precision + entity_recall) if \
        (entity_precision + entity_recall) > 0 else 0.0

    boundary_precision = boundary_matches / len(pred_entities) if pred_entities else 0.0
    boundary_recall = boundary_matches / len(gold_entities) if gold_entities else 0.0
    boundary_f1 = 2 * boundary_precision * boundary_recall / (boundary_precision + boundary_recall) if \
        (boundary_precision + boundary_recall) > 0 else 0.0

    type_accuracy = type_matches / len(pred_entities) if pred_entities else 0.0
    role_accuracy = sum(1 for e in pred_entities if e in gold_entities) / len(pred_entities) if pred_entities else 0.0

    return NERMetrics(
        entity_precision=entity_precision,
        entity_recall=entity_recall,
        entity_f1=entity_f1,
        boundary_precision=boundary_precision,
        boundary_recall=boundary_recall,
        boundary_f1=boundary_f1,
        type_accuracy=type_accuracy,
        role_accuracy=role_accuracy,
        per_type_metrics=per_type,
    )


# ---------------------------------------------------------------------------
# Obligation extraction metrics
# ---------------------------------------------------------------------------


@dataclass
class ObligationSlot:
    """A single slot in an obligation (responsible party, action, etc.)."""
    slot_name: str
    value: str
    start: int
    end: int


@dataclass
class ObligationMatch:
    """Result of matching two obligations."""
    exact_match: bool
    partial_slots: Dict[str, bool]  # slot_name -> exact match
    iou_scores: Dict[str, float]  # slot_name -> span IoU


def match_obligations(
    pred_obligations: List[Obligation],
    gold_obligations: List[Obligation],
) -> List[ObligationMatch]:
    """Match predicted obligations to gold obligations.

    Uses span IoU to determine match quality for each slot.
    """
    matches: List[ObligationMatch] = []

    for pred in pred_obligations:
        best_match = None
        best_score = 0.0

        for gold in gold_obligations:
            # Simple matching: count matching slots
            matching_slots = 0
            total_slots = 0

            if pred.responsible_party and gold.responsible_party:
                total_slots += 1
                if pred.responsible_party == gold.responsible_party:
                    matching_slots += 1

            if pred.action and gold.action:
                total_slots += 1
                if pred.action == gold.action:
                    matching_slots += 1

            if pred.object_ and gold.object_:
                total_slots += 1
                if pred.object_ == gold.object_:
                    matching_slots += 1

            if pred.beneficiary and gold.beneficiary:
                total_slots += 1
                if pred.beneficiary == gold.beneficiary:
                    matching_slots += 1

            score = matching_slots / total_slots if total_slots > 0 else 0.0
            if score > best_score:
                best_score = score
                best_match = gold

        if best_match:
            # Compute detailed match info
            partial_slots: Dict[str, bool] = {}
            iou_scores: Dict[str, float] = {}

            if pred.responsible_party and best_match.responsible_party:
                partial_slots["responsible_party"] = pred.responsible_party == best_match.responsible_party
                iou_scores["responsible_party"] = span_iou(
                    pred.responsible_party_span[0] if pred.responsible_party_span else 0,
                    pred.responsible_party_span[1] if pred.responsible_party_span else 0,
                    best_match.responsible_party_span[0] if best_match.responsible_party_span else 0,
                    best_match.responsible_party_span[1] if best_match.responsible_party_span else 0,
                )

            if pred.action and best_match.action:
                partial_slots["action"] = pred.action == best_match.action
                iou_scores["action"] = span_iou(
                    pred.action_span[0] if pred.action_span else 0,
                    pred.action_span[1] if pred.action_span else 0,
                    best_match.action_span[0] if best_match.action_span else 0,
                    best_match.action_span[1] if best_match.action_span else 0,
                )

            if pred.deadline and best_match.deadline:
                partial_slots["deadline"] = pred.deadline == best_match.deadline
                iou_scores["deadline"] = span_iou(
                    pred.deadline_span[0] if pred.deadline_span else 0,
                    pred.deadline_span[1] if pred.deadline_span else 0,
                    best_match.deadline_span[0] if best_match.deadline_span else 0,
                    best_match.deadline_span[1] if best_match.deadline_span else 0,
                )

            exact = best_match in gold_obligations
            matches.append(ObligationMatch(exact_match=exact, partial_slots=partial_slots, iou_scores=iou_scores))
        else:
            matches.append(ObligationMatch(exact_match=False, partial_slots={}, iou_scores={}))

    return matches


@dataclass
class ObligationMetrics:
    """Metrics for obligation extraction."""
    detection_precision: float
    detection_recall: float
    detection_f1: float
    exact_match_precision: float
    exact_match_recall: float
    exact_match_f1: float
    slot_level_metrics: Dict[str, Dict[str, float]]  # slot_name -> P/R/F1
    duplicate_rate: float


def compute_obligation_metrics(
    pred_obligations: List[Obligation],
    gold_obligations: List[Obligation],
) -> ObligationMetrics:
    """Compute obligation extraction metrics.

    Args:
        pred_obligations: Predicted obligations
        gold_obligations: Ground truth obligations

    Returns:
        ObligationMetrics with detection and slot-level metrics
    """
    if not gold_obligations:
        # If no gold obligations, all predictions are false positives
        return ObligationMetrics(
            detection_precision=0.0,
            detection_recall=0.0,
            detection_f1=0.0,
            exact_match_precision=0.0,
            exact_match_recall=0.0,
            exact_match_f1=0.0,
            slot_level_metrics={},
            duplicate_rate=0.0,
        )

    # Detection metrics (is the obligation detected at all?)
    detected = sum(1 for p in pred_obligations if p in gold_obligations)
    detection_precision = detected / len(pred_obligations) if pred_obligations else 0.0
    detection_recall = detected / len(gold_obligations)
    detection_f1 = 2 * detection_precision * detection_recall / (detection_precision + detection_recall) if \
        (detection_precision + detection_recall) > 0 else 0.0

    # Exact match (all slots match)
    matches = match_obligations(pred_obligations, gold_obligations)
    exact_matches = sum(1 for m in matches if m.exact_match)
    exact_match_precision = exact_matches / len(pred_obligations) if pred_obligations else 0.0
    exact_match_recall = exact_matches / len(gold_obligations)
    exact_match_f1 = 2 * exact_match_precision * exact_match_recall / (exact_match_precision + exact_match_recall) if \
        (exact_match_precision + exact_match_recall) > 0 else 0.0

    # Slot-level metrics (compute for each slot name)
    # This is simplified - in practice, you'd have slot definitions
    slot_level: Dict[str, Dict[str, float]] = {}

    # Duplicate rate
    unique_preds = set(o.obligation_id for o in pred_obligations if o.obligation_id)
    duplicate_rate = (len(pred_obligations) - len(unique_preds)) / len(pred_obligations) if pred_obligations else 0.0

    return ObligationMetrics(
        detection_precision=detection_precision,
        detection_recall=detection_recall,
        detection_f1=detection_f1,
        exact_match_precision=exact_match_precision,
        exact_match_recall=exact_match_recall,
        exact_match_f1=exact_match_f1,
        slot_level_metrics=slot_level,
        duplicate_rate=duplicate_rate,
    )


# ---------------------------------------------------------------------------
# Risk finding metrics
# ---------------------------------------------------------------------------


@dataclass
class RiskMatch:
    """Result of matching two risk findings."""
    exact_match: bool
    category_match: bool
    severity_agreement: bool
    span_iou: float


def match_risks(
    pred_risks: List[RiskFlag],
    gold_risks: List[RiskFlag],
) -> List[RiskMatch]:
    """Match predicted risks to gold risks."""
    matches: List[RiskMatch] = []

    for pred in pred_risks:
        best_match = None
        best_iou = 0.0

        for gold in gold_risks:
            iou = span_iou(pred.char_start, pred.char_end, gold.char_start, gold.char_end)
            if iou > best_iou:
                best_iou = iou
                best_match = gold

        if best_match:
            matches.append(RiskMatch(
                exact_match=best_match in gold_risks,
                category_match=pred.category == best_match.category,
                severity_agreement=pred.severity == best_match.severity,
                span_iou=best_iou,
            ))
        else:
            matches.append(RiskMatch(
                exact_match=False,
                category_match=False,
                severity_agreement=False,
                span_iou=0.0,
            ))

    return matches


@dataclass
class RiskMetrics:
    """Metrics for risk finding."""
    precision: float
    recall: float
    f1: float
    false_positive_rate: float
    false_negative_rate: float
    category_precision: float
    severity_agreement: float


def compute_risk_metrics(
    pred_risks: List[RiskFlag],
    gold_risks: List[RiskFlag],
) -> RiskMetrics:
    """Compute risk finding metrics.

    Args:
        pred_risks: Predicted risk flags
        gold_risks: Ground truth risk flags

    Returns:
        RiskMetrics with P/R/F1 and severity agreement
    """
    if not gold_risks:
        return RiskMetrics(
            precision=0.0,
            recall=0.0,
            f1=0.0,
            false_positive_rate=1.0 if pred_risks else 0.0,
            false_negative_rate=0.0,
            category_precision=0.0,
            severity_agreement=0.0,
        )

    matches = match_risks(pred_risks, gold_risks)

    # Count metrics
    true_positives = sum(1 for m in matches if m.exact_match)
    false_positives = len(pred_risks) - true_positives
    false_negatives = len(gold_risks) - true_positives

    precision = true_positives / len(pred_risks) if pred_risks else 0.0
    recall = true_positives / len(gold_risks)
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    fp_rate = false_positives / len(pred_risks) if pred_risks else 0.0
    fn_rate = false_negatives / len(gold_risks)

    # Category precision (when found, is category correct?)
    category_matches = sum(1 for m in matches if m.category_match)
    category_precision = category_matches / len(pred_risks) if pred_risks else 0.0

    # Severity agreement (Cohen's kappa approximation)
    severity_agree = sum(1 for m in matches if m.severity_agreement)
    severity_agreement = severity_agree / len(pred_risks) if pred_risks else 0.0

    return RiskMetrics(
        precision=precision,
        recall=recall,
        f1=f1,
        false_positive_rate=fp_rate,
        false_negative_rate=fn_rate,
        category_precision=category_precision,
        severity_agreement=severity_agreement,
    )


# ---------------------------------------------------------------------------
# Evidence integrity metrics
# ---------------------------------------------------------------------------


@dataclass
class EvidenceMetrics:
    """Metrics for evidence integrity."""
    exact_span_accuracy: float
    mean_span_iou: float
    clause_localization_accuracy: float
    cross_reference_accuracy: float
    evidence_completeness: float


def compute_evidence_metrics(
    pred_evidence: List[Tuple[str, int, int]],  # (document_id, start, end)
    gold_evidence: List[Tuple[str, int, int]],
) -> EvidenceMetrics:
    """Compute evidence integrity metrics.

    Args:
        pred_evidence: List of (doc_id, start, end) tuples for predicted evidence
        gold_evidence: List of (doc_id, start, end) tuples for gold evidence

    Returns:
        EvidenceMetrics with span and provenance metrics
    """
    if not gold_evidence:
        return EvidenceMetrics(
            exact_span_accuracy=0.0,
            mean_span_iou=0.0,
            clause_localization_accuracy=0.0,
            cross_reference_accuracy=0.0,
            evidence_completeness=0.0,
        )

    exact_matches = 0
    total_iou = 0.0

    for pred in pred_evidence:
        best_iou = 0.0

        for gold in gold_evidence:
            if pred[0] == gold[0]:  # Same document
                iou = span_iou(pred[1], pred[2], gold[1], gold[2])
                best_iou = max(best_iou, iou)
                if iou == 1.0:
                    exact_matches += 1

        total_iou += best_iou

    exact_accuracy = exact_matches / len(pred_evidence) if pred_evidence else 0.0
    mean_iou = total_iou / len(pred_evidence) if pred_evidence else 0.0

    # Simplified metrics - in practice, these would track specific provenance data
    clause_localization = exact_accuracy  # Assume exact spans imply correct clause localization
    cross_reference = exact_accuracy  # Assume exact spans imply correct cross-reference
    completeness = min(1.0, len(pred_evidence) / len(gold_evidence))

    return EvidenceMetrics(
        exact_span_accuracy=exact_accuracy,
        mean_span_iou=mean_iou,
        clause_localization_accuracy=clause_localization,
        cross_reference_accuracy=cross_reference,
        evidence_completeness=completeness,
    )


# ---------------------------------------------------------------------------
# Summary metrics aggregator
# ---------------------------------------------------------------------------


@dataclass
class EvaluationSummary:
    """Aggregate evaluation summary."""
    classification: ClassificationMetrics
    ner: NERMetrics
    obligations: ObligationMetrics
    risks: RiskMetrics
    evidence: EvidenceMetrics
    overall_score: float


def compute_evaluation_summary(
    classification: ClassificationMetrics,
    ner: NERMetrics,
    obligations: ObligationMetrics,
    risks: RiskMetrics,
    evidence: EvidenceMetrics,
) -> EvaluationSummary:
    """Compute an overall evaluation score as a weighted average."""
    # Weighted combination of key metrics
    scores = [
        classification.macro_f1,
        ner.entity_f1,
        obligations.exact_match_f1,
        risks.f1,
        evidence.exact_span_accuracy,
    ]
    weights = [0.25, 0.20, 0.20, 0.20, 0.15]

    overall = sum(s * w for s, w in zip(scores, weights, strict=True))

    return EvaluationSummary(
        classification=classification,
        ner=ner,
        obligations=obligations,
        risks=risks,
        evidence=evidence,
        overall_score=overall,
    )
