# Evaluation Workstream — Autonomous Session 20261103

Subagent session on the BharatContract AI repo (`main`, base `f0bad0a`).
Scope: rules-vs-hybrid comparison, abstention, family-disjoint held-out
evaluation, dataset license/provenance, and tests. Local commits only (no
push, no history rewrite). Gold annotations and the integrated baseline JSON
were **not** modified.

## Commits (local)

| SHA | Summary |
|---|---|
| `5900bc6` | rules-vs-hybrid script + family-split module + shared classifier metrics |
| `a95a5c4` | rules-vs-hybrid + risk-booster delta reports; held-out script |
| `e36de67` | family-disjoint held-out evaluation + leakage analysis + tests |
| `e32914c` | family-leakage report (7/102 test docs leak) + cached leakage |
| `24d6117` | dataset license/provenance report (CUAD + MAUD) |
| *(this)*  | workstream summary |

## What I built / changed (files I own)

- `scripts/eval_rules_vs_hybrid.py` — rule-only vs hybrid classifier on the
  train corpus + ML risk-booster delta (full pipeline ×2).
- `scripts/eval_heldout.py` — family-disjoint held-out evaluation
  (`--leakage-only` writes just the leakage artifact).
- `nlp/evaluation/family_split.py` — CUAD template-family detection
  (title + 8-gram shingle near-duplicate proxy) + `leakage_report_cached`.
- `nlp/evaluation/classifier_metrics.py` — shared multi-label P/R/F1,
  confusion matrix, abstention helpers.
- `tests/test_evaluation_family_split.py`, `tests/test_rules_vs_hybrid.py`.
- Reports: `rules_vs_hybrid_20261103.{json,md}`,
  `risk_booster_delta_20261103.md`, `heldout_family_disjoint_20261103.{json,md}`,
  `cuad_family_leakage_20261103.{json,md}`, `dataset_provenance_20261103.md`.

**No `app/` changes** — the risk-booster "disabled" run is produced by hiding
`nlp.risk_scoring.risk_model._CACHED` (the one-per-process model cache), which
makes `_augment_with_ml_risks` no-op exactly as when no artefact is present.
This is the cleanest available switch and requires no production-code change.

## Actual metric numbers (quoted, labeled honestly)

### 1. Rules-only vs hybrid — IN-DISTRIBUTION training corpus
Banner (verbatim in report): *"IN-DISTRIBUTION TRAINING-CORPUS COMPARISON —
NOT A GENERALIZATION ESTIMATE. CUAD is a US dataset; template-family
separation from the keyword-bank source documents is not guaranteed."*
Input: 2,000-row deterministic sample (seed 20261103) of
`data/processed/clause_classifier.csv` (9,278 rows, manifest-verified train-only).
Active components: rule engine (2,021 keyword patterns incl. CUAD bank,
provenance=verified) **and** TF-IDF model (14 labels, present). Both the model
and the keyword bank are trained from this same corpus, so these numbers are
**doubly optimistic** and are NOT a generalization estimate.

| Mode | Acc@1 | Acc@3 | Macro-F1@1 | Weighted-F1@1 | Macro-F1@3 | Weighted-F1@3 |
|---|---|---|---|---|---|---|
| rule-only | 0.3370 | 0.4080 | 0.2367 | 0.3818 | 0.2542 | 0.4110 |
| hybrid | 0.9160 | 0.9860 | 0.8560 | 0.9167 | 0.4134 | 0.7951 |

- Mode delta: top-1 label changed on 1,308/2,000 (65.4%); the hybrid
  re-labelled 638 rows that rule-only had mis-filed as `Miscellaneous`.
- **Abstention:** rule-only never returns an empty label list — its
  "abstention" is the `Miscellaneous` fallback (642/2000, 32.1%); hybrid's
  empty-after-0.15-threshold abstention is 0/2000 (the fallback top-1 always
  fires). The distribution of abstained/fallback items over gold categories is
  in the report (this is "what we give up when abstaining").

### 2. ML risk-booster delta — full pipeline ×2 on 300 CUAD TRAIN clause texts
| Measure | Value |
|---|---|
| Rule-only findings (booster off) | 1,531 |
| **ML_RISK_001 findings added** | **63** |
| ML findings on already-rule-flagged clauses (redundant) | 0 |
| Clauses whose risk_score changed | 63 / 580 |
| Clauses whose risk_level changed | 63 / 580 |
| Documents whose overall score/level changed | 60 / 300 |

Every added finding is `source="model"`, `evidence_status="unverified"`, an
uncalibrated review prompt — not a verified finding. (Note: the rule-flag
count varies slightly across runs because a sibling agent modified
`nlp/risk_scoring/rules.py` mid-session; the ML-added count is stable at 63.)

### 3. Family-disjoint held-out evaluation — CUAD test, family-disjoint
Banner (verbatim in report): *"CUAD test split, family-disjoint by title+shingle
proxy; US contracts; category set differs from the internal 26-label taxonomy
(mapped via nlp/taxonomy.py); results indicate in-dataset generalization
within CUAD only."*
Set: 95/102 test documents whose template family has no train presence;
5,039 CUAD-annotated clause examples. This is the **closest thing to a
legitimate generalization estimate** this project can produce, and it is still
in-dataset (CUAD only).

| Mode | Acc@1 | Acc@3 | Macro-F1@1 | Weighted-F1@1 | Macro-F1@3 | Weighted-F1@3 |
|---|---|---|---|---|---|---|
| rule-only | 0.1840 | 0.2526 | 0.1314 | 0.1978 | 0.1373 | 0.2164 |
| hybrid | 0.4009 | 0.5324 | 0.4034 | 0.4133 | 0.2046 | 0.3680 |

The big drop from the in-distribution numbers (hybrid 0.916 → 0.401 Acc@1)
is the honest signal: the earlier 0.916 was training-overlap, not
generalization. Rule-only is weak on held-out data (0.184 Acc@1); the hybrid
TF-IDF model carries most of the generalization.

### 4. Family-leakage findings (exact counts)
Proxy: exact normalised-title equality OR ≥50% overlap of 8-char shingles
(fraction of the smaller set). Train 408 docs / 375 families; test 102 docs /
99 families.
- **Test docs whose family also appears in train (leaked, excluded): 7/102** —
  all 7 are title-equality leaks (same EDGAR filing identifier re-filed).
- **Test docs family-disjoint from train (realistic held-out set): 95/102.**
- Reverse: **14 train docs** share a family with a test doc (train-side
  near-copy concern).
- The official CUAD 80/20 split was **not** family-disjoint; evaluating on the
  raw test split overstates generalization for those 7 documents.

### 5. Dataset license/provenance
- **No LICENSE/README exists under `data/datasets/`** for either dataset.
  License is **unverified in-repo — verify before redistribution**. The prior
  "CC BY 4.0" claim (phase_2c report) is marked an **unverified prior claim**
  (upstream Atticus/HF docs not verifiable from this checkout).
- CUAD: 510 docs (408 train / 102 test), 41 categories, US EDGAR filings;
  supports US clause mention-detection / classifier training; does NOT
  support Indian-law compliance.
- MAUD: 25,827/6,753/6,651 rows (train/dev/test) over 153 contracts, 7
  categories, US merger agreements; rows are **not independent documents**;
  does NOT support Indian-law compliance.

## Verification

- `uv run pytest tests/ -q` → **560 passed, 6 warnings, 0 failed** (all green,
  including my 14 new tests).
- `uv run ruff check` on all my files → clean.
- `scripts/eval_rules_vs_hybrid.py` → exit 0 (writes JSON+MD + risk delta).
- `scripts/eval_heldout.py` → exit 0 (full + `--leakage-only`); leakage is
  cached (`tmp/family_leakage_cache.json`) so re-runs are ~5s.

## Non-claims / honesty

- No metric here is an Indian-law correctness measure (both datasets are US).
- The in-distribution numbers are training-overlap, not generalization.
- Family separation is a template proxy, not legal independence.
- Gold labels are CUAD's own QA annotations (taxonomy-mapped), not independent
  human adjudication.

## Could not do / caveats

- **True EDGAR/SEC filing-family identity** was not verified (no network);
  the title+shingle proxy is a practical stand-in and is labeled as such.
- The **risk-booster delta rule-flag count** is sensitive to the parallel
  `rules.py` edits from a sibling agent (1,270 in my first run → 1,531 after
  their P1 fix); the **ML-added count (63) is stable** and is the number that
  matters for the booster's marginal contribution.
- I did **not** add a `RISK_ML_BOOSTER_ENABLED` settings flag (the task
  permitted but did not require it); hiding the model cache is a strictly
  smaller change and avoids touching `app/core/config.py` + `analyzer.py`.
