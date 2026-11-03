# Evaluation Framework

This directory contains the evaluation infrastructure for BharatContract AI.

> ## ⚠️ What these metrics can and cannot tell you
>
> **Gold annotations are derived from the pipeline + manual adjudication on 17
> synthetic cases; they support BEHAVIOUR regression checking, NOT accuracy
> claims.** The synthetic corpus is not ground truth from real contracts, so
> integrated scores (classification/NER/obligation/risk/evidence) measure
> conformance to the pipeline's own labelled expectations, not legal or
> predictive accuracy. See `DEEP_AUDIT_20261103.md` §2.4 (findings C1–C2).

## Components

### Core Modules

| File | Purpose |
|------|---------|
| `harness.py` | Main execution engine for evaluation cases |
| `cases.py` | 17 synthetic evaluation contracts |
| `metrics.py` | Core evaluation metrics implementation |
| `metrics_integration.py` | Computes integrated metrics against `gold_annotations/cases_gold.json` |
| `regression_detector.py` | Regression detection against a committed baseline |
| `gold_annotations/cases_gold.json` | Gold annotations (verified against real case text + real engine rule IDs) |

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
| CUAD | `data/datasets/cuad/` | Available (license per dataset documentation in `data/datasets/` — verify before redistribution) |
| MAUD | `data/datasets/maud/` | Available (license per dataset documentation in `data/datasets/` — verify before redistribution) |
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
| Synthetic Cases | see `reports/evaluations/synthetic_eval_results.md` (run `uv run python scripts/run_evaluation.py`) — 17/17 (as of 2026-11-03, commit be1359f) |
| Test suite | see `uv run pytest tests/ -q` (as of 2026-11-03, commit be1359f: 262) |
| Provenance Verification | 0 failures (as of 2026-11-03, commit be1359f) |
| Ruff Linting | Clean (as of 2026-11-03, commit be1359f) |

### Known Limitations

1. **Synthetic vs Real**: Current harness uses synthetic contracts; real-world evaluation requires legal reviewer input
2. **Label Coverage**: Some clause types may have insufficient training examples
3. **Indian Law Coverage**: Datasets are US-oriented; Indian contract patterns require expansion

## Next Steps

1. **Expand Evaluation Corpus**: Add real Indian contracts with legal reviewer validation
2. **Cross-Validation**: Implement k-fold cross-validation for robust estimates
3. **Error Analysis**: Document false positives/negatives for improvement targeting
4. **Human Evaluation**: Design expert review protocol for legal accuracy assessment
