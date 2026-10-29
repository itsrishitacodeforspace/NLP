# Defect Register — BharatContract AI

## Fixed

### D1 — TC-05 fixture not shipped (fresh-checkout failure)
Two tests failed on a fresh clone (`DocumentParseError`). Fix: tracked `tests/fixtures/TC-05_cross_reference_traps.md`; location-independent path. Commit `66684a1`.

### D2 — `.ua/` scratch committed (lint blocker)
`ruff check .` reported 16 errors on a fresh clone, all `.ua/`. Fix: gitignored `.ua/`, untracked 63 files. Commit `8bbbe47`.

### D3 — `data/processed/` regeneration undocumented
Fresh clone silently lost the CUAD keyword bank; accuracy/provenance tests skipped. Fix: README documents `build_training_data.py` + `BCC_EVAL_MODE=ci`. Commit `ae55c59`.

### D4 — T1b exact-text overlap invariant was incorrect
T1b flagged 24/9278 rows; all `split=train`, 0 contamination (boilerplate + near-duplicate filings). Fix: rewritten to source-lineage assertion. See `T1B_DIAGNOSIS.md`. Commit `c2df667`.

### D5 — Indemnification clause mislabeled as "Limitation of Liability"
Spurious "Missing liability cap" alongside "Uncapped liability". Fix: `rule_uncapped_liability` skips indemnification-heading clauses. Commit `fe75ef2`.

### D6 — "Missing stamp duty / TDS" reported as confirmed defect on keyword absence
These rules fired CRITICAL/MEDIUM when the entity was merely not detected, presenting "not found" as "confirmed absent" and inflating every Indian contract's score. Fix: reframed as "not found — verify" review prompts; STAMP CRITICAL→MEDIUM, TDS MEDIUM→LOW; verified case-law pointers kept. Regression: `tests/test_risk_rules.py`. Commit `e2468c8`.

### D7 — Obligations lacked traceable source offsets
`Obligation` had no `char_start`/`char_end`, so a finding could not be traced to the source sentence.
Fix: zero-based, end-exclusive offsets into the clause text; `Obligation.text` is the exact source
slice. Repeated or non-unique sentences leave offsets `None` (no fabricated location). Regression:
`test_offsets_are_exact_source_slices`, `test_repeated_sentences_leave_offsets_unknown`.

### D8 — Conditional text polluted subject/action/deadline
Leading "If … ," became the subject; a mid-sentence condition made `action="if"`; condition deadlines
leaked into `deadline_expression`; a protasis modal could win over the main clause. Fix: condition
spans are masked before subject/action/deadline extraction, the main-clause modal is chosen after a
leading-condition comma, and deadlines are read from the masked text. Regressions cover leading,
mid, trailing (unless), multiple conditions, `Subject to Clause 5`, protasis modals, and passive voice.

### D9 — Beneficiary/counterparty was missing or greedy
No beneficiary was extracted; a naive pattern produced `"Supplier INR 100000"`. Fix: conservative
dative/`to X` extraction with role nouns, corporate names, and 2+ capitalised proper names; explicit
`to X` beats a possessive direct object; self-recipients are skipped; optional `party_aliases` maps
defined names to canonical labels. Ambiguous recipients stay `None`. Regression:
`test_beneficiary_recipient_patterns`, `test_counterparty_is_not_greedy_around_amounts`,
`test_party_alias_is_canonicalised_without_losing_source_name`.

### D10 — Uncalibrated ML score presented as "confidence"
`ML_RISK_001` formatted raw `predict_proba` as a confidence percentage. Fix: renamed to
"Model-suggested …" and the explanation now says "uncalibrated model score … (raw classifier output,
not a calibrated probability)". Calibration itself remains open. Regression:
`test_analyzer_augmentation_adds_model_finding` asserts the new wording and absence of "confidence".

### D11 — Section 124 checked the whole contract for direct-loss wording
The contract-level rule scanned all clause text, so an unrelated "breach of contract" or "direct
losses" mention suppressed the Section 124 review prompt. Fix: evaluate only indemnification
clauses, preserve `evidence_status="unverified"`, and record an indemnity-specific `search_scope`.
Regression: `test_s124_not_suppressed_by_unrelated_breach_of_contract_language`.

## Open
- P3 four-way missing-protection status is represented only implicitly by existing `RiskFlag`
  fields; there is no explicit status enum or consumer.
- ML risk score remains uncalibrated (`ML_RISK_001`); only the misleading presentation is fixed.
- Whole-contract cross-reference reasoning not consumed (P4); prior suppression reverted as unsafe.
- No-comma leading conditions leave the responsible party `None` (ambiguous without a parser).
