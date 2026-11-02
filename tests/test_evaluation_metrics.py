"""Tests for evaluation metrics in nlp/evaluation/metrics.py."""
from __future__ import annotations

import pytest

from nlp.evaluation.metrics import (
    compute_classification_metrics,
    compute_evidence_metrics,
    compute_ner_metrics,
    span_exact_match,
    span_iou,
)


class TestSpanMetrics:
    """Tests for span-based utilities."""

    def test_span_iou_exact_match(self) -> None:
        """IoU should be 1.0 for identical spans."""
        assert span_iou(0, 10, 0, 10) == 1.0

    def test_span_iou_no_overlap(self) -> None:
        """IoU should be 0.0 for non-overlapping spans."""
        assert span_iou(0, 5, 10, 15) == 0.0

    def test_span_iou_partial_overlap(self) -> None:
        """IoU should be correct for partial overlap."""
        # [0, 10] and [5, 15] overlap on [5, 10] = 5 chars
        # Total = 10 + 10 - 5 = 15
        assert span_iou(0, 10, 5, 15) == 5 / 15

    def test_span_iou_empty_span(self) -> None:
        """IoU should be 0.0 for empty spans."""
        assert span_iou(0, 0, 5, 10) == 0.0
        assert span_iou(0, 10, 0, 0) == 0.0

    def test_span_exact_match_exact(self) -> None:
        """Should return True for exact match."""
        assert span_exact_match(0, 10, 0, 10) is True

    def test_span_exact_match_different(self) -> None:
        """Should return False for different spans."""
        assert span_exact_match(0, 10, 0, 11) is False
        assert span_exact_match(0, 10, 1, 10) is False


class TestClassificationMetrics:
    """Tests for classification metrics."""

    def test_perfect_classification(self) -> None:
        """Perfect classification should give 1.0 metrics."""
        predictions = ["A", "B", "C"]
        ground_truth = ["A", "B", "C"]
        all_labels = ["A", "B", "C"]

        metrics = compute_classification_metrics(predictions, ground_truth, all_labels)

        assert metrics.precision == 1.0
        assert metrics.recall == 1.0
        assert metrics.f1 == 1.0
        assert metrics.macro_f1 == 1.0
        assert metrics.micro_f1 == 1.0

    def test_perfect_per_class_metrics(self) -> None:
        """Per-class metrics should be 1.0 for perfect classification."""
        predictions = ["A", "B", "C"]
        ground_truth = ["A", "B", "C"]
        all_labels = ["A", "B", "C"]

        metrics = compute_classification_metrics(predictions, ground_truth, all_labels)

        for label in all_labels:
            assert metrics.per_class_metrics[label]["precision"] == 1.0
            assert metrics.per_class_metrics[label]["recall"] == 1.0
            assert metrics.per_class_metrics[label]["f1"] == 1.0

    def test_classification_confusion_matrix(self) -> None:
        """Confusion matrix should be populated correctly."""
        predictions = ["A", "A", "B"]
        ground_truth = ["A", "B", "B"]
        all_labels = ["A", "B"]

        metrics = compute_classification_metrics(predictions, ground_truth, all_labels)

        # Confusion matrix entries
        assert metrics.confusion_matrix[("A", "A")] == 1  # TP for A
        assert metrics.confusion_matrix[("A", "B")] == 1  # FP for A / FN for B
        assert metrics.confusion_matrix[("B", "B")] == 1  # TP for B

    def test_abstention_count(self) -> None:
        """Should count abstentions correctly."""
        predictions = ["A", "unclassified", "B", "unclassified"]
        ground_truth = ["A", "B", "B", "B"]
        all_labels = ["A", "B"]

        metrics = compute_classification_metrics(predictions, ground_truth, all_labels)

        assert metrics.abstention_count == 2
        assert metrics.total_count == 4

    def test_partial_classification(self) -> None:
        """Should compute correct metrics for partial classification."""
        predictions = ["A", "A", "B", "C"]
        ground_truth = ["A", "B", "B", "C"]
        all_labels = ["A", "B", "C"]

        metrics = compute_classification_metrics(predictions, ground_truth, all_labels)

        # A: pred[0]=A,gold[0]=A (TP=1), pred[1]=A,gold[1]=B (FP=1), FN=0
        assert metrics.per_class_metrics["A"]["tp"] == 1
        assert metrics.per_class_metrics["A"]["fp"] == 1
        assert metrics.per_class_metrics["A"]["fn"] == 0

        # B: pred[1]=A,gold[1]=B (FN=1), pred[2]=B,gold[2]=B (TP=1), FP=0
        assert metrics.per_class_metrics["B"]["tp"] == 1
        assert metrics.per_class_metrics["B"]["fp"] == 0
        assert metrics.per_class_metrics["B"]["fn"] == 1

        # C: pred[3]=C,gold[3]=C (TP=1), FP=0, FN=0
        assert metrics.per_class_metrics["C"]["tp"] == 1
        assert metrics.per_class_metrics["C"]["fp"] == 0
        assert metrics.per_class_metrics["C"]["fn"] == 0

        # Macro F1 should be average of per-class F1s
        a_f1 = metrics.per_class_metrics["A"]["f1"]
        b_f1 = metrics.per_class_metrics["B"]["f1"]
        c_f1 = metrics.per_class_metrics["C"]["f1"]
        expected_macro = (a_f1 + b_f1 + c_f1) / 3
        assert metrics.macro_f1 == pytest.approx(expected_macro)


class TestNERMetrics:
    """Tests for NER metrics."""

    def test_perfect_ner(self) -> None:
        """Perfect NER should give 1.0 metrics."""
        from nlp.evaluation.metrics import Entity

        pred_entities = [
            Entity(entity_id="e1", text="John", start=0, end=4, entity_type="PERSON"),
            Entity(entity_id="e2", text="Company", start=5, end=12, entity_type="ORG"),
        ]
        gold_entities = pred_entities.copy()
        all_entity_types = ["PERSON", "ORG", "DATE"]

        metrics = compute_ner_metrics(pred_entities, gold_entities, all_entity_types)

        assert metrics.entity_precision == 1.0
        assert metrics.entity_recall == 1.0
        assert metrics.entity_f1 == 1.0
        assert metrics.boundary_precision == 1.0
        assert metrics.boundary_recall == 1.0
        assert metrics.boundary_f1 == 1.0

    def test_partial_entity_match(self) -> None:
        """Should handle partial entity matches."""
        from nlp.evaluation.metrics import Entity

        pred_entities = [
            Entity(entity_id="e1", text="John", start=0, end=4, entity_type="PERSON"),
        ]
        gold_entities = [
            Entity(entity_id="e1", text="John Smith", start=0, end=10, entity_type="PERSON"),
        ]
        all_entity_types = ["PERSON", "ORG"]

        metrics = compute_ner_metrics(pred_entities, gold_entities, all_entity_types)

        # Precision should be < 1.0 (wrong boundary)
        assert metrics.entity_precision < 1.0
        # Recall should be < 1.0 (missed part of entity)
        assert metrics.entity_recall < 1.0

    def test_entity_boundary_accuracy(self) -> None:
        """Should compute boundary accuracy correctly."""
        from nlp.evaluation.metrics import Entity

        pred_entities = [
            Entity(entity_id="e1", text="John", start=0, end=4, entity_type="PERSON"),
            Entity(entity_id="e2", text="Company", start=5, end=12, entity_type="ORG"),
        ]
        gold_entities = [
            Entity(entity_id="e1", text="John", start=0, end=4, entity_type="PERSON"),
            Entity(entity_id="e2", text="Company Ltd", start=5, end=16, entity_type="ORG"),
        ]
        all_entity_types = ["PERSON", "ORG"]

        metrics = compute_ner_metrics(pred_entities, gold_entities, all_entity_types)

        # Boundaries match only for first entity
        assert metrics.boundary_precision == 0.5
        assert metrics.boundary_recall == 0.5

    def test_per_type_metrics(self) -> None:
        """Should compute per-type metrics correctly."""
        from nlp.evaluation.metrics import Entity

        pred_entities = [
            Entity(entity_id="e1", text="John", start=0, end=4, entity_type="PERSON"),
            Entity(entity_id="e2", text="Company", start=5, end=12, entity_type="ORG"),
        ]
        gold_entities = [
            Entity(entity_id="e1", text="John", start=0, end=4, entity_type="PERSON"),
            Entity(entity_id="e2", text="Corp", start=5, end=9, entity_type="ORG"),
        ]
        all_entity_types = ["PERSON", "ORG", "DATE"]

        metrics = compute_ner_metrics(pred_entities, gold_entities, all_entity_types)

        # PERSON: TP=1
        assert metrics.per_type_metrics["PERSON"]["tp"] == 1
        assert metrics.per_type_metrics["PERSON"]["precision"] == 1.0
        assert metrics.per_type_metrics["PERSON"]["recall"] == 1.0

        # ORG: TP=0, FP=1, FN=1
        assert metrics.per_type_metrics["ORG"]["tp"] == 0
        assert metrics.per_type_metrics["ORG"]["fp"] == 1
        assert metrics.per_type_metrics["ORG"]["fn"] == 1

        # DATE: all zeros
        assert metrics.per_type_metrics["DATE"]["tp"] == 0


class TestEvidenceMetrics:
    """Tests for evidence integrity metrics."""

    def test_perfect_evidence(self) -> None:
        """Perfect evidence spans should give 1.0 metrics."""
        pred_evidence = [("doc1", 0, 100)]
        gold_evidence = [("doc1", 0, 100)]

        metrics = compute_evidence_metrics(pred_evidence, gold_evidence)

        assert metrics.exact_span_accuracy == 1.0
        assert metrics.mean_span_iou == 1.0
        assert metrics.evidence_completeness == 1.0

    def test_partial_evidence(self) -> None:
        """Partial span matches should give lower scores."""
        pred_evidence = [("doc1", 0, 50)]
        gold_evidence = [("doc1", 0, 100)]

        metrics = compute_evidence_metrics(pred_evidence, gold_evidence)

        # IoU = 50/100 = 0.5
        assert metrics.mean_span_iou == 0.5
        # Exact match = 0
        assert metrics.exact_span_accuracy == 0.0

    def test_no_gold_evidence(self) -> None:
        """All metrics should be 0 when no gold exists."""
        pred_evidence = [("doc1", 0, 100)]
        gold_evidence: list[tuple[str, int, int]] = []

        metrics = compute_evidence_metrics(pred_evidence, gold_evidence)

        assert metrics.exact_span_accuracy == 0.0
        assert metrics.mean_span_iou == 0.0

    def test_multiple_documents(self) -> None:
        """Should handle evidence across multiple documents."""
        pred_evidence = [("doc1", 0, 50), ("doc2", 0, 50)]
        gold_evidence = [("doc1", 0, 100), ("doc2", 0, 100)]

        metrics = compute_evidence_metrics(pred_evidence, gold_evidence)

        # Each has IoU = 0.5
        assert metrics.mean_span_iou == 0.5
        assert metrics.exact_span_accuracy == 0.0


class TestIntegration:
    """Integration tests for the evaluation framework."""

    def test_metrics_consistency(self) -> None:
        """Test that metrics are consistent across edge cases."""
        # Empty inputs should handle gracefully
        metrics = compute_classification_metrics([], [], ["A", "B"])
        assert metrics.total_count == 0

        # Single element
        metrics = compute_classification_metrics(["A"], ["A"], ["A", "B"])
        assert metrics.precision == 1.0
        assert metrics.recall == 1.0
        assert metrics.f1 == 1.0

    def test_span_iou_symmetry(self) -> None:
        """IoU should be symmetric: IoU(a,b) == IoU(b,a)."""
        assert span_iou(0, 10, 5, 15) == span_iou(5, 15, 0, 10)
        assert span_iou(10, 20, 15, 25) == span_iou(15, 25, 10, 20)

    def test_perfect_classifier_with_abstentions(self) -> None:
        """Classifier with abstentions should have lower overall metrics."""
        predictions = ["A", "B", "unclassified"]
        ground_truth = ["A", "B", "C"]
        all_labels = ["A", "B", "C", "unclassified"]

        metrics = compute_classification_metrics(predictions, ground_truth, all_labels)

        # Perfect for detected classes
        assert metrics.per_class_metrics["A"]["f1"] == 1.0
        assert metrics.per_class_metrics["B"]["f1"] == 1.0

        # Unseen class should have zero
        assert metrics.per_class_metrics["C"]["f1"] == 0.0
        assert metrics.per_class_metrics["unclassified"]["f1"] == 0.0

        # Abstention count
        assert metrics.abstention_count == 1


# ---------------------------------------------------------------------------
# Adversarial tests (edge cases not covered by basic tests)
# ---------------------------------------------------------------------------


class TestAdversarialNER:
    """Adversarial tests for NER metrics - empty sets, duplicates, partial spans."""

    def test_ner_empty_predictions(self) -> None:
        """Empty predictions with non-empty gold should give 0 metrics."""
        from nlp.evaluation.metrics import Entity

        pred_entities: list[Entity] = []
        gold_entities = [Entity(entity_id="e1", text="John", start=0, end=4, entity_type="PERSON")]
        all_entity_types = ["PERSON", "ORG"]

        metrics = compute_ner_metrics(pred_entities, gold_entities, all_entity_types)

        # Precision is undefined when no predictions; should be 0
        assert metrics.entity_precision == 0.0
        # Recall should be 0 (no correct predictions out of gold entities)
        assert metrics.entity_recall == 0.0
        assert metrics.entity_f1 == 0.0

    def test_ner_empty_gold(self) -> None:
        """Non-empty predictions with empty gold should give 0 metrics."""
        from nlp.evaluation.metrics import Entity

        pred_entities = [Entity(entity_id="e1", text="John", start=0, end=4, entity_type="PERSON")]
        gold_entities: list[Entity] = []
        all_entity_types = ["PERSON", "ORG"]

        metrics = compute_ner_metrics(pred_entities, gold_entities, all_entity_types)

        # Precision should be 0 (no gold to match)
        assert metrics.entity_precision == 0.0
        # Recall is undefined when no gold; should be 0
        assert metrics.entity_recall == 0.0
        assert metrics.entity_f1 == 0.0

    def test_ner_duplicate_predictions(self) -> None:
        """Duplicate predictions should be counted separately (penalized)."""
        from nlp.evaluation.metrics import Entity

        entity = Entity(entity_id="e1", text="John", start=0, end=4, entity_type="PERSON")
        pred_entities = [entity, entity]  # Same entity twice
        gold_entities = [entity]
        all_entity_types = ["PERSON", "ORG"]

        metrics = compute_ner_metrics(pred_entities, gold_entities, all_entity_types)

        # Without set deduplication in TP/FP/FN: 1 exact match / 2 predictions = 0.5 precision
        # Recall is 1.0 (1 match / 1 gold)
        assert metrics.entity_precision == 0.5  # 1/2
        assert metrics.entity_recall == 1.0  # 1/1
        # F1 = 2 * 0.5 * 1.0 / (0.5 + 1.0) = 0.666...
        assert metrics.entity_f1 == pytest.approx(2/3)

    def test_ner_partial_span_start(self) -> None:
        """Different start, same end should not be exact match."""
        from nlp.evaluation.metrics import Entity

        pred_entities = [
            Entity(entity_id="e1", text="ohn", start=1, end=4, entity_type="PERSON"),  # 1-4
        ]
        gold_entities = [
            Entity(entity_id="e1", text="John", start=0, end=4, entity_type="PERSON"),  # 0-4
        ]
        all_entity_types = ["PERSON", "ORG"]

        metrics = compute_ner_metrics(pred_entities, gold_entities, all_entity_types)

        # Should not be exact match (different start)
        assert metrics.entity_precision == 0.0
        assert metrics.entity_recall == 0.0

    def test_ner_different_end_same_start(self) -> None:
        """Same start, different end should not be exact match."""
        from nlp.evaluation.metrics import Entity

        pred_entities = [
            Entity(entity_id="e1", text="Joh", start=0, end=3, entity_type="PERSON"),  # 0-3
        ]
        gold_entities = [
            Entity(entity_id="e1", text="John", start=0, end=4, entity_type="PERSON"),  # 0-4
        ]
        all_entity_types = ["PERSON", "ORG"]

        metrics = compute_ner_metrics(pred_entities, gold_entities, all_entity_types)

        # Should not be exact match (different end)
        assert metrics.entity_precision == 0.0
        assert metrics.entity_recall == 0.0


class TestAdversarialClassification:
    """Adversarial tests for classification metrics."""

    def test_classification_all_abstentions(self) -> None:
        """All abstentions should result in 0 metrics."""
        predictions = ["unclassified", "unclassified"]
        ground_truth = ["A", "B"]
        all_labels = ["A", "B", "unclassified"]

        metrics = compute_classification_metrics(predictions, ground_truth, all_labels)

        assert metrics.abstention_count == 2
        # No true positives, no predicted positives -> P/R/F1 = 0
        assert metrics.precision == 0.0
        assert metrics.recall == 0.0
        assert metrics.f1 == 0.0

    def test_classification_complete_mismatch(self) -> None:
        """All predictions wrong should result in 0 metrics."""
        predictions = ["A", "A", "A"]
        ground_truth = ["B", "B", "B"]
        all_labels = ["A", "B"]

        metrics = compute_classification_metrics(predictions, ground_truth, all_labels)

        # No true positives at all
        assert metrics.precision == 0.0
        assert metrics.recall == 0.0
        assert metrics.f1 == 0.0
        # All predictions are false positives for A
        assert metrics.per_class_metrics["A"]["fp"] == 3
        # All ground truth are false negatives for B
        assert metrics.per_class_metrics["B"]["fn"] == 3
        # Confusion matrix should show all A->B
        assert metrics.confusion_matrix[("A", "B")] == 3
