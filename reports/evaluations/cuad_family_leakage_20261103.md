# CUAD Family Leakage Report — 20261103

> **This measures template-family separation, NOT legal independence.**
> Family proxy = (a) exact normalised-title equality across splits, or (b)
> ≥ 50% overlap of 8-character shingles (fraction of the smaller shingle set)
> between the whole documents. The machine-readable data is in
> `cuad_family_leakage_20261103.json` (full report from `scripts/eval_heldout.py`).

## Method

- **Title proxy:** CUAD document titles are EDGAR-style filing identifiers
  (`COMPANY_date_form_exhibit_CONTRACT TYPE`). Documents with the same
  normalised title are the same template family (e.g. the same contract
  re-filed in a later amendment).
- **Shingle proxy:** two documents are in the same family if they share at
  least 50% of 8-character shingles of the smaller document (parameterised
  in `nlp/evaluation/family_split.py`, `FamilyMap(threshold=...)`). This
  catches near-identical templates whose titles differ slightly.
- **Limitations:** (1) the title is a proxy for SEC-filing identity, not a
  verified filing; (2) shingle similarity measures textual near-duplication,
  not legal independence — two documents from disjoint families can still
  share boilerplate, jurisdiction, or party; (3) the 50% threshold is a
  hyperparameter: lower thresholds group more documents into families (more
  conservative held-out set), higher thresholds the reverse.

## Results (threshold = 0.5)

| Measure | Count |
|---|---|
| Train documents | 408 (across 375 families) |
| Test documents | 102 (across 99 families) |
| **Test docs whose family also appears in train (leaked — excluded)** | **7** |
| **Test docs family-disjoint from train (realistic held-out set)** | **95** |
| Reverse: train docs whose family appears in test | 14 |

### Leaked test documents (excluded from the held-out evaluation)

1. `AFSALABANCORPINC_08_01_1996-EX-1.1-AGENCY AGREEMENT`
2. `GALERATHERAPEUTICS,INC_02_14_2020-EX-99.A-JOINT FILING AGREEMENT`
3. `IdeanomicsInc_20151124_8-K_EX-10.2_9354744_EX-10.2_Content License Agreement`
4. `N2KINC_10_16_1997-EX-10.16-SPONSORSHIP AGREEMENT`
5. `PaperexchangeComInc_20000322_S-1A_EX-10.4_5202103_EX-10.4_Co-Branding Agreement`
6. `SPOKHOLDINGS,INC_06_19_2020-EX-10.1-COOPERATION AGREEMENT`
7. `WOMENSGOLFUNLIMITEDINC_03_29_2000-EX-10.13-ENDORSEMENT AGREEMENT`

(All 7 are title-equality leaks: the identical filing identifier appears in
`train_separate_questions.json`.)

### Reverse overlap (train docs whose family appears in test) — 14 docs

Notable: `WOMENSGOLFUNLIMITEDINC_03_29_2000-EX-10.13-ENDORSEMENT AGREEMENT`
appears in both splits (title-equality). The rest are near-duplicate template
pairs (agency agreements, joint filing agreements, sponsorship agreements,
co-branding agreements) — same template family across splits.

## Interpretation

- The official CUAD 80/20 split was **not** family-disjoint: ~7% of test
  documents (7/102) share a template family with a train document. Evaluating
  on the raw test split overstates generalization for those 7 documents.
- The 95 family-disjoint test documents (5,039 clause examples) are the
  realistic held-out set used by `scripts/eval_heldout.py` — see
  `heldout_family_disjoint_20261103.md` for the classifier metrics on them.
- 14 train documents also share families with test documents: if a model was
  trained on the full train split, it saw a near-copy of those templates.
  This is a **train-side** concern (it slightly reduces the effective
  independence of the training set) and is reported for completeness.

## Non-claims

- This is a proxy-based estimate. True SEC-filing-family identity would
  require matching against EDGAR (not done here; no network access).
- Shingle-based near-duplication is not legal independence.
- Nothing here supports a claim about Indian-law or out-of-CUAD generalization.
