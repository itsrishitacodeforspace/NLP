# Model retraining report — train-only classifiers (2026-11-03)

> Status: **training-set diagnostics only.** Nothing in this report is a
> generalization estimate, an Indian-law correctness claim, or a benchmark.
> A provenance manifest proves data lineage only — never accuracy.

## Why this was done

The bundled classifiers (`models/tfidf_classifier.7z`, `models/risk_classifier.7z`)
were trained on the **full** CUADv1 corpus (train ∪ test) — a documented
leakage — while `data/processed/` had been restored to **train-only**
artifacts. The models were never retrained from the clean data, so the shipped
model and the clean data did not agree. This retraining closes that gap: both
classifiers are now trained **only** from the train-only, manifest-verified
corpus.

## What was trained on

**Corpus:** `data/processed/clause_classifier.csv`

- sha256: `03241d80becff51ec441bd531b8ece1b04101f3900283a57506cef11e14bdcb9`
- manifest: `artifact_sha256` matches the file; `row_count` 9,278; every row
  `split=train`; single source `data/datasets/cuad/train_separate_questions.json`
  (sha256 `7de21d2bb741ac939e2a839ef9640634a5e0f9f40ea2b82c6833baf7db33dab4`,
  `split=train`). Verified by `scripts/verify_provenance.py` (0 failures).
- rows: 9,278 (all canonical taxonomy labels); source docs: 408 (CUAD train).
- class distribution (TF-IDF target):

| category | rows |
|---|---|
| Definitions | 1760 |
| Intellectual Property | 1192 |
| Assignment | 973 |
| Term and Renewal | 860 |
| Payment Terms | 853 |
| Non-Compete / Non-Solicit | 687 |
| Limitation of Liability | 682 |
| Termination | 565 |
| Audit Rights | 536 |
| Insurance | 443 |
| Governing Law | 372 |
| Warranty | 154 |
| Miscellaneous | 153 |
| Confidentiality | 48 |

**Risk weak-label distribution** (labels from the rule engine + a mild,
max-MEDIUM clause-type prior; see "Risk model changes" below):

| severity | rows |
|---|---|
| low | 5451 |
| medium | 2705 |
| high | 1122 |

(No `critical` weak labels: the rule engine assigns critical only to specific
triggers, none of which fire on these corpus snippets.)

## Pipeline shape (unchanged)

- **TF-IDF clause classifier:** TF-IDF (ngram 1-2, min_df 2, max_df 0.95,
  sublinear_tf, english stop words) + LogisticRegression
  (`class_weight="balanced"`, `C=4.0`). Solver changed `liblinear` → `lbfgs`
  because liblinear cannot fit >2 classes and this corpus has 14.
- **Risk classifier:** TF-IDF (same params) + LogisticRegression
  (`class_weight="balanced"`, `C=1.0`, `lbfgs`), unchanged from before.
- Labels are canonicalised to `nlp.taxonomy.INTERNAL_LABELS` (non-canonical
  labels dropped; legacy `Pricing Terms` → `Payment Terms` alias applied).
  0 rows were dropped on this corpus (all 9,278 are already canonical).

## Risk model changes (honesty fixes)

1. **Severity-prior inflation removed.** `nlp.risk_scoring.risk_model._TYPE_BASELINE`
   previously labelled **every** `Limitation of Liability` and `Indemnification`
   clause `HIGH` by type alone. It is now capped at `MEDIUM` for all
   high-scrutiny types. Rationale: a clause *type* alone must not teach the
   model that all LoL/Indemnity clauses are high risk — that made the weak
   supervision severity-inflated by construction and would make the recall
   booster fire on routine boilerplate. Real severity still comes from rule
   triggers (which win when they fire).
2. **Weak-supervision wording kept.** The model docstring and the `ML_RISK_001`
   finding text still state the model is *weakly supervised*, a *recall
   booster*, and its score is *not a calibrated probability*.

## Training-set metrics (IN-SAMPLE ONLY — not a generalization estimate)

These are computed on data the model was trained on. They measure in-distribution
consistency, **not** performance on unseen contracts. Do not cite them as
accuracy.

### TF-IDF clause classifier

- **Full training set (9,278 rows), top-1: 0.9230.**
- Stratified 85/15 split (random_state=42), top-1 on the 1,392-row split:
  accuracy **0.82**, macro F1 **0.82**.

Per-class (full training set):

| category | precision | recall | f1 | support |
|---|---|---|---|---|
| Assignment | 0.96 | 0.91 | 0.94 | 973 |
| Audit Rights | 0.97 | 0.99 | 0.98 | 536 |
| Confidentiality | 0.92 | 0.94 | 0.93 | 48 |
| Definitions | 0.94 | 0.90 | 0.92 | 1760 |
| Governing Law | 0.99 | 1.00 | 0.99 | 372 |
| Insurance | 0.98 | 0.98 | 0.98 | 443 |
| Intellectual Property | 0.93 | 0.90 | 0.92 | 1192 |
| Limitation of Liability | 0.98 | 0.95 | 0.97 | 682 |
| Miscellaneous | 0.94 | 0.94 | 0.94 | 153 |
| Non-Compete / Non-Solicit | 0.85 | 0.91 | 0.88 | 687 |
| Payment Terms | 0.96 | 0.96 | 0.96 | 853 |
| Term and Renewal | 0.81 | 0.86 | 0.83 | 860 |
| Termination | 0.84 | 0.92 | 0.88 | 565 |
| Warranty | 0.91 | 0.98 | 0.94 | 154 |

`macro avg 0.93 / 0.94 / 0.93` · `weighted avg 0.92 / 0.92 / 0.92`.

### Risk classifier

- **Full training set (9,278 rows), top-1 (weak labels): 0.9610.**
- Stratified 85/15 split, top-1 on the 1,392-row split: accuracy **0.90**,
  macro F1 **0.89**.

Per-class (full training set, weak labels):

| severity | precision | recall | f1 | support |
|---|---|---|---|---|
| high | 0.94 | 0.98 | 0.96 | 1122 |
| low | 0.98 | 0.96 | 0.97 | 5451 |
| medium | 0.93 | 0.96 | 0.95 | 2705 |

`macro avg 0.95 / 0.97 / 0.96` · `weighted avg 0.96 / 0.96 / 0.96`.

## Category coverage (12 empty categories)

No data was fabricated. `nlp/datasets/coverage.py` reports, for all 26
`INTERNAL_LABELS`, how many training rows exist in `clause_classifier.csv`.

- **ML-supported (14 of 26):** the categories above — the only labels the TF-IDF
  model can emit.
- **Rule-only (0 training rows, 12):** Indemnification, Data Protection,
  Dispute Resolution, Force Majeure, Compliance, Service Levels, Change
  Control, Notice, Acceptance, Stamp Duty, TDS / GST, Arbitration Seat. These
  are detected by the rule classifier only (every Indian-specific category is
  100% rule-dependent — there are no gold labels for them).

The classifier's module docstring (`nlp/clause_classification/tfidf_model.py`)
now lists this split, and `scripts/eval_classifier.py` prints it.

## Document-disjointness (split-family) check

CUAD's own train/test split is by document:

- `train_separate_questions.json`: 408 docs. `test.json`: 102 docs.
- **Title overlap: 0. Full-text (normalized) overlap: 0.** i.e. the documents
  are disjoint by ID and by full text (already asserted by
  `tests/test_no_leakage.py::test_t1d_source_lineage_train_and_held_out_are_disjoint`).
- **Near-duplicate heuristic** (word 8-gram overlap, report-only): 3 of 408
  training docs share >50% of their 8-grams with some held-out doc; aggregate
  overlap 3.7%. This is a heuristic, not a proof.

**Honest statement:** documents are disjoint by ID and by full text, but
**template-family (near-duplicate) separation is NOT guaranteed** — CUAD comes
from SEC filings where boilerplate legitimately repeats across documents. No
leakage-free, family-disjoint held-out set exists in this repo, so no
leakage-free evaluation was possible.

## Explicit non-claims

- **No generalization estimate.** Every number above is in-sample
  (training-set only). No leakage-free CUAD held-out set exists, so there is
  no out-of-distribution or generalization number in this repo for either
  model.
- **No Indian-law validity.** The corpus is US CUAD filings. Nothing here
  supports a claim that either model is correct for Indian contracts. The
  12 rule-only categories are the ones that matter most for the product, and
  they have no ML training data at all.
- **Weak supervision.** The risk classifier's labels come from the rule engine,
  not gold severity data. Its high in-sample "accuracy" largely reflects that
  it is learning to reproduce the rule engine's output on the same phrasings.
- **US corpus only.** 14 of 26 taxonomy categories; all 12 Indian-specific /
  operational categories are rule-only.

## Old vs. new artifact hashes

| artifact | old (leaky, pre-retrain) | new (train-only) |
|---|---|---|
| `models/tfidf_classifier.7z` (sha256) | `6bf3840cdc19aca2cae6510a3f6335719e31c816f2e394108699374ee8cafcda` | `67652195ab6d7f0c9adaaad443330c6ae51582b655c98b83050d6253ba3a9e10` |
| `models/risk_classifier.7z` (sha256) | `e03616822cd767af871d7a424c6b5ba3fd66fd2fea0166c4fb00ceb39bc5cb3a` | `958b5e01c0daa0773015854069203c775d68e57dcf6a353bca018ced7ea9bcd1` |
| tfidf `cache_sha256` (joblib) | `87c60eebca94b40f25c5d4403b3d6991b6467bc85e91422c252cddd0141003ae` | `ef8b0167d31187f86e17aa1f6d8f9e6e181f57aaecdc8cbc7513f3c32cf5742c` |
| risk `cache_sha256` (joblib) | `b40ed2b20d2eb8e8ea423e63ce2fe9f062897641aeafa916dbfa3add4447b4ce` | `014592bd708a3fedc5fbd90a1931ad2c336b7538fff146e440624637855f46fc` |

`models/PROVENANCE_STATUS.json` now marks both archives `train-only-verified`
with the new `cache_sha256` values and a precise reason. The status is a
data-lineage statement (train-only, manifest-verified) and **not** an accuracy
claim.

## `eval_classifier.py` output (new model, banner "EXPLORATORY - NOT A BENCHMARK")

Top-1 over the first 2,000 corpus rows (training-overlapping — **not** a
generalization metric):

```
EXPLORATORY - NOT A BENCHMARK
A manifest proves data lineage only; it never proves accuracy or predictive validity.
Taxonomy coverage (training rows in this corpus): 14 of 26 categories ML-supported;
rule-only (0 rows): Indemnification, Data Protection, Dispute Resolution, Force
Majeure, Compliance, Service Levels, Change Control, Notice, Acceptance, Stamp Duty,
TDS / GST, Arbitration Seat
  input: data/processed/clause_classifier.csv
  sha256: 03241d80becff51ec441bd531b8ece1b04101f3900283a57506cef11e14bdcb9
  provenance: verified
  row_count: 9278

Top-1 accuracy over 2000 rows: 92.4%
```

## Reproduce

```bash
uv run python scripts/train_tfidf_classifier.py   # -> models/tfidf_classifier.joblib + .7z + status
uv run python scripts/train_risk_classifier.py    # -> models/risk_classifier.joblib + .7z + status
uv run python scripts/eval_classifier.py          # banner + per-category diagnostic
uv run python scripts/verify_provenance.py        # 0 failures
```
