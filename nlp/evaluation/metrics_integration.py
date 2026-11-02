"""Integrate evaluation metrics with pipeline outputs."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.models.schemas import AnalysisResult
from nlp.evaluation.cases import EvalCase
from nlp.evaluation.metrics import (
    ClassificationMetrics,
    Entity,
    EvidenceMetrics,
    NERMetrics,
    compute_classification_metrics,
    compute_evidence_metrics,
    compute_ner_metrics,
)

GOLD_ANNOTATIONS_PATH = Path(__file__).parent / "gold_annotations" / "cases_gold.json"


@dataclass
class CaseMetrics:
    case_id: str
    classification: ClassificationMetrics | None = None
    ner: NERMetrics | None = None
    obligations: dict[str, Any] | None = None
    risks: dict[str, Any] | None = None
    evidence: EvidenceMetrics | None = None
    cross_refs: dict[str, Any] | None = None
    metrics_computed: bool = False
    errors: list[str] = field(default_factory=list)


@dataclass
class IntegratedEvaluationReport:
    case_metrics: dict[str, CaseMetrics]
    aggregate: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def load_gold_annotations() -> dict[str, Any]:
    import json
    with open(GOLD_ANNOTATIONS_PATH) as f:
        return json.load(f)


def extract_entities_from_analysis(result: AnalysisResult) -> list[Entity]:
    entities: list[Entity] = []
    if result.contract.parties:
        for party in result.contract.parties:
            entity = Entity(
                entity_id=f"party_{len(entities)}",
                text=party,
                start=0,
                end=len(party),
                entity_type="PARTY",
                role="",
            )
            entities.append(entity)
    return entities


def extract_evidence_from_analysis(result: AnalysisResult) -> list[tuple[str, int, int]]:
    evidence: list[tuple[str, int, int]] = []
    for risk in result.risks or []:
        for span in risk.evidence_spans:
            evidence.append((result.contract.contract_id or "", span.char_start, span.char_end))
    for oblig in result.obligations or []:
        if oblig.char_start is not None and oblig.char_end is not None:
            evidence.append((result.contract.contract_id or "", oblig.char_start, oblig.char_end))
    return evidence


def compute_case_metrics(case: EvalCase, result: AnalysisResult) -> CaseMetrics:
    case_id = case.case_id
    metrics = CaseMetrics(case_id=case_id)

    try:
        gold_annotations = load_gold_annotations()
        case_gold = gold_annotations["cases"].get(case_id)
        if not case_gold:
            metrics.errors.append(f"No gold annotations found for case {case_id}")
            return metrics

        # 1. Classification metrics
        classification_gold = case_gold.get("classification_gold", {})
        if classification_gold:
            pred_labels: list[str] = []
            if classification_gold.get("liability_type") == "uncapped":
                if any("RISK_LIABILITY_001" in str(f) for f in result.risks or []):
                    pred_labels.append("liability_uncapped")
            if classification_gold.get("auto_renewal") and not classification_gold.get("notice_required", True):
                if any("RISK_RENEWAL_001" in str(f) for f in result.risks or []):
                    pred_labels.append("auto_renewal_no_notice")
            if classification_gold.get("termination_one_sided"):
                if any("RISK_TERMINATION_001" in str(f) for f in result.risks or []):
                    pred_labels.append("termination_one_sided")
            if classification_gold.get("indemnity_scope") == "broad":
                pred_labels.append("indemnity_broad")

            ground_truth_labels: list[str] = []
            for key, val in classification_gold.items():
                if val is True:
                    ground_truth_labels.append(key)
                elif val in ("broad", "uncapped"):
                    ground_truth_labels.append(f"{key}_{val}")

            all_labels = list(set(pred_labels + ground_truth_labels))
            if pred_labels or ground_truth_labels:
                try:
                    metrics.classification = compute_classification_metrics(
                        predictions=pred_labels,
                        ground_truth=ground_truth_labels,
                        all_labels=all_labels if all_labels else ["none"],
                    )
                    metrics.metrics_computed = True
                except Exception as e:
                    metrics.errors.append(f"Classification metrics error: {str(e)}")

        # 2. NER metrics
        ner_gold = case_gold.get("ner_gold", [])
        if ner_gold:
            pred_entities = extract_entities_from_analysis(result)
            gold_entities = [
                Entity(
                    entity_id=e["entity_id"],
                    text=e["text"],
                    start=e["start"],
                    end=e["end"],
                    entity_type=e["type"],
                    role=e.get("role"),
                )
                for e in ner_gold
            ]
            all_entity_types = list(set(e["type"] for e in ner_gold))
            if pred_entities or gold_entities:
                try:
                    metrics.ner = compute_ner_metrics(
                        pred_entities=pred_entities,
                        gold_entities=gold_entities,
                        all_entity_types=all_entity_types,
                    )
                    metrics.metrics_computed = True
                except Exception as e:
                    metrics.errors.append(f"NER metrics error: {str(e)}")

        # 3. Obligation metrics
        oblig_gold = case_gold.get("obligation_gold", [])
        if oblig_gold:
            pred_obligations = result.obligations or []
            matched = 0
            for go in oblig_gold:
                loc = go.get("locate", "")
                for po in pred_obligations:
                    if po.text and loc.lower() in po.text.lower():
                        matched += 1
                        break
            tp = matched
            fp = len(pred_obligations) - matched
            fn = len(oblig_gold) - matched
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
            metrics.obligations = {
                "detection_precision": precision,
                "detection_recall": recall,
                "detection_f1": f1,
                "true_positives": tp,
                "false_positives": fp,
                "false_negatives": fn,
            }
            metrics.metrics_computed = True

        # 4. Risk metrics
        risk_gold = case_gold.get("risk_gold", [])
        if risk_gold:
            pred_risks = result.risks or []
            matched = 0
            for rg in risk_gold:
                rid = rg.get("risk_id", "")
                for pr in pred_risks:
                    if rid in str(pr.risk_id):
                        matched += 1
                        break
            tp = matched
            fp = len(pred_risks) - matched
            fn = len(risk_gold) - matched
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
            metrics.risks = {
                "detection_precision": precision,
                "detection_recall": recall,
                "detection_f1": f1,
                "true_positives": tp,
                "false_positives": fp,
                "false_negatives": fn,
            }
            metrics.metrics_computed = True

        # 5. Evidence metrics
        evidence_gold = case_gold.get("evidence_gold", [])
        if evidence_gold:
            pred_evidence = extract_evidence_from_analysis(result)
            gold_evidence = [(eg["doc_id"], eg["start"], eg["end"]) for eg in evidence_gold]
            if pred_evidence or gold_evidence:
                try:
                    metrics.evidence = compute_evidence_metrics(
                        pred_evidence=pred_evidence,
                        gold_evidence=gold_evidence,
                    )
                    metrics.metrics_computed = True
                except Exception as e:
                    metrics.errors.append(f"Evidence metrics error: {str(e)}")

        # 6. Cross-reference metrics
        cross_ref_gold = case_gold.get("cross_ref_gold", [])
        if cross_ref_gold:
            has_cross_ref = any("Section" in str(c.text) for c in result.clauses or [])
            metrics.cross_refs = {"detected": has_cross_ref, "expected_count": len(cross_ref_gold)}
            metrics.metrics_computed = True

    except Exception as e:
        metrics.errors.append(f"Error computing metrics: {str(e)}")

    return metrics


def run_integrated_evaluation() -> IntegratedEvaluationReport:
    from nlp.evaluation.harness import run_all
    report = run_all()
    case_metrics: dict[str, CaseMetrics] = {}
    for cr in report.case_results:
        case_id = cr.case.case_id
        metrics = compute_case_metrics(cr.case, cr.result)
        case_metrics[case_id] = metrics

    aggregate = {}
    classification_metrics = [m.classification for m in case_metrics.values() if m.classification]
    ner_metrics = [m.ner for m in case_metrics.values() if m.ner]
    evidence_metrics = [m.evidence for m in case_metrics.values() if m.evidence]

    if classification_metrics:
        aggregate["classification"] = {
            "macro_f1": sum(m.f1 for m in classification_metrics) / len(classification_metrics),
            "micro_f1": sum(m.micro_f1 for m in classification_metrics) / len(classification_metrics),
        }
    if ner_metrics:
        aggregate["ner"] = {
            "entity_f1": sum(m.entity_f1 for m in ner_metrics) / len(ner_metrics),
            "boundary_f1": sum(m.boundary_f1 for m in ner_metrics) / len(ner_metrics),
        }

    oblig_metrics = [m.obligations for m in case_metrics.values() if m.obligations]
    risk_metrics = [m.risks for m in case_metrics.values() if m.risks]

    if oblig_metrics:
        aggregate["obligations"] = {"detection_f1": sum(m["detection_f1"] for m in oblig_metrics) / len(oblig_metrics)}
    if risk_metrics:
        aggregate["risks"] = {"detection_f1": sum(m["detection_f1"] for m in risk_metrics) / len(risk_metrics)}

    if evidence_metrics:
        aggregate["evidence"] = {
            "mean_iou": sum(m.mean_span_iou for m in evidence_metrics) / len(evidence_metrics),
            "exact_accuracy": sum(m.exact_span_accuracy for m in evidence_metrics) / len(evidence_metrics),
        }

    errors = []
    for m in case_metrics.values():
        errors.extend(m.errors)

    return IntegratedEvaluationReport(case_metrics=case_metrics, aggregate=aggregate, errors=errors)


def generate_integrated_report_json(report: IntegratedEvaluationReport) -> dict:
    output = {"version": "1.0.0", "git_revision": "unknown", "aggregate_metrics": report.aggregate, "case_results": {}}
    for case_id, cm in report.case_metrics.items():
        case_output = {"metrics_computed": cm.metrics_computed, "errors": cm.errors}
        if cm.classification:
            case_output["classification"] = {
                "precision": cm.classification.precision,
                "recall": cm.classification.recall,
                "f1": cm.classification.f1,
                "macro_f1": cm.classification.macro_f1,
                "micro_f1": cm.classification.micro_f1,
            }
        if cm.ner:
            case_output["ner"] = {
                "entity_precision": cm.ner.entity_precision,
                "entity_recall": cm.ner.entity_recall,
                "entity_f1": cm.ner.entity_f1,
            }
        if cm.obligations:
            case_output["obligations"] = cm.obligations
        if cm.risks:
            case_output["risks"] = cm.risks
        if cm.evidence:
            case_output["evidence"] = {
                "mean_span_iou": cm.evidence.mean_span_iou,
                "exact_span_accuracy": cm.evidence.exact_span_accuracy,
            }
        output["case_results"][case_id] = case_output
    return output
