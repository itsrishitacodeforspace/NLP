# Evaluation Framework

This directory contains the evaluation infrastructure for BharatContract AI.

## Components

### Core Modules

| File | Purpose |
|------|---------|
| `harness.py` | Main execution engine for evaluation cases |
| `cases.py` | 17 synthetic evaluation contracts |
| `metrics.py` | Core evaluation metrics implementation |
| `reporter.py` | Report generation for evaluation results |
| `baseline.py` | Baseline measurements for regression detection |

### Tests

| File | Purpose |
|------|---------|
| `tests/test_evaluation_harness.py` | Regression tests for synthetic corpus |
| `tests/test_evaluation_metrics.py` | Unit tests for metric calculations |
| `tests/test_classifier_accuracy.py` | Classifier accuracy tests |
| `tests/test_audit_integration.py` | Integration defect tests (D1-D6) |

## Metrics Implemented

### 1. Classification Metrics (`ClassificationMetrics`)

- **Precision/Recall/F1**: Per-class and micro/macro averages
- **Confusion Matrix**: Predicted vs actual label counts
- **Abstention Rate**: Rate of unclassified clauses
- **Macro F1**: Unweighted average of per-class F1 scores
- **Micro F1**: Global TP/FP/FN aggregated

### 2. NER Metrics (`NERMetrics`)

- **Entity-level P/R/F1**: Exact entity match (type + span)
- **Boundary P/R/F1**: Span match regardless of type
- **Type Accuracy**: Entity type accuracy
- **Role Accuracy**: Party-role assignment accuracy
- **Per-Type Metrics**: Breakdown by entity type

### 3. Obligation Metrics (`ObligationMetrics`)

- **Detection P/R/F1**: Is the obligation detected at all?
- **Exact Match P/R/F1**: All slots match exactly
- **Slot-Level Metrics**: Per-slot precision/recall
- **Duplicate Rate**: Rate of duplicate obligations

### 4. Risk Metrics (`RiskMetrics`)

- **Precision/Recall/F1**: Risk finding accuracy
- **False Positive/Negative Rates**: Error breakdown
- **Category Precision**: When found, is category correct?
- **Severity Agreement**: Severity rating agreement

### 5. Evidence Metrics (`EvidenceMetrics`)

- **Exact Span Accuracy**: Character-offset match rate
- **Mean Span IoU**: Average intersection-over-union
- **Clause Localization**: Correct clause identification
- **Cross-Reference Accuracy**: Reference resolution quality
- **Evidence Completeness**: Proportion of evidence found

## Usage

### Run the Evaluation Harness

```bash
# Run all synthetic cases
uv run python scripts/run_evaluation.py

# Run with specific output directory
uv run python scripts/run_evaluation.py --output reports/evaluations/20261102

# Run specific cases
uv run python scripts/run_evaluation.py --cases 1,3,5
```

### Compute Metrics Programmatically

```python
from nlp.evaluation.metrics import (
    compute_classification_metrics,
    compute_ner_metrics,
    compute_obligation_metrics,
    compute_risk_metrics,
    compute_evidence_metrics,
)

# Classification example
predictions = ["Payment Terms", "Limitation of Liability", "Termination"]
ground_truth = ["Payment Terms", "Limitation of Liability", "Indemnification"]
all_labels = ["Payment Terms", "Limitation of Liability", "Termination", "Indemnification", ...]

metrics = compute_classification_metrics(predictions, ground_truth, all_labels)
print(f"Macro F1: {metrics.macro_f1:.3f}")
```

## Dataset Integrity

### Current Datasets

| Dataset | Location | Status |
|---------|----------|--------|
| CUAD | `data/datasets/cuad/` | Available (MIT-like license) |
| MAUD | `data/datasets/maud/` | Available (Apache 2.0) |
| Processed Classification | `data/processed/clause_classifier.csv` | 9,278 rows |
| Processed CUAD Examples | `data/processed/cuad_examples.jsonl` | 22,450 rows |
| Processed MAUD Examples | `data/processed/maud_examples.jsonl` | 32,580 rows |

### Data Provenance

Run the provenance verifier:

```bash
uv run python scripts/verify_provenance.py
```

Expected output: `0 failure(s), 0 skipped`

## Evaluation Results

### Current Baseline

| Metric | Value |
|--------|-------|
| Synthetic Cases | 17/17 passing |
| Integration Tests | 228 passing |
| Provenance Verification | 0 failures |
| Ruff Linting | Clean |

### Known Limitations

1. **Synthetic vs Real**: Current harness uses synthetic contracts; real-world evaluation requires legal reviewer input
2. **Label Coverage**: Some clause types may have insufficient training examples
3. **Indian Law Coverage**: Datasets are US-oriented; Indian contract patterns require expansion

## Next Steps

1. **Expand Evaluation Corpus**: Add real Indian contracts with legal reviewer validation
2. **Cross-Validation**: Implement k-fold cross-validation for robust estimates
3. **Error Analysis**: Document false positives/negatives for improvement targeting
4. **Human Evaluation**: Design expert review protocol for legal accuracy assessment
