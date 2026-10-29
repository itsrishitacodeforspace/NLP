# Recovery Tracker — BharatContract AI

Last updated: 2026-10-29

## State
- Branch `main`; verification baseline `97f4c21` (14 local commits ahead of
  `origin/main` `a1b4298`). This docs-only update follows that baseline. Nothing pushed.
- Clean verification worktree: repo-local `tmp/bcc-clean-97f4c21` at `97f4c21`.
  Main-tree user WIP remains uncommitted and untouched.
- Historical fresh-checkout validation: `tmp/freshcheckout` at `118e8ae` (superseded by the
  current clean run below).

## Commits this session
- `66684a1` fix(tests): ship TC-05 synthetic fixture for fresh-checkout reproducibility
- `8bbbe47` chore: remove committed .ua scratch and gitignore it
- `ae55c59` docs: document data/processed regeneration for fresh clones
- `c2df667` test(provenance): assert source lineage, not exact-text overlap, in T1b
- `fe75ef2` fix(risk): don't treat indemnification clauses as limitation-of-liability
- `e2468c8` fix(risk): mark stamp-duty and TDS "not found" as review, not confirmed defect
- `3ec86b6` fix(risk): qualify S124 indemnity finding and document scoring heuristic
- `d6e3f69` feat(risk): add advisory cross-reference analysis to findings
- `118e8ae` fix(obligations): populate deadline_date, handle passive voice, written-out deadlines
- `0cf396a` fix(obligations): add source offsets, conditions, beneficiary; clarify ML score
- `975512b` fix(risk): scope S124 check to indemnity clauses
- `f1bf4f4` docs(recovery): record S124 scope fix and current verification
- `be51191` docs: add final project report

## Verified clean workflow — current HEAD (2026-10-29)
Starting HEAD: `97f4c21`. Worktree: repo-local `tmp/bcc-clean-97f4c21`.

1. `uv sync --extra dev` → exit 0 (154 packages, Python 3.12.14)
2. `uv run ruff check .` → "All checks passed!"
3. `uv run python scripts/build_training_data.py` → exit 0; 9,278 rows, 5 manifests
4. `uv run python scripts/verify_provenance.py` → **0 failures, 0 skipped**
5. `$env:BCC_EVAL_MODE='ci'; uv run pytest -q` → **exit 0** (129 tests at HEAD)
6. `uv run python scripts/run_demo.py` → exit 0 (12 clauses, 13 obligations, score 100.0/critical)
7. API smoke: `tests/test_api_smoke.py` passed in the full suite. A direct `uvicorn` launch
   for `/healthz` and `/docs` was blocked by `dcg`; it was not run.

## Provenance diagnosis at current HEAD
- Main tree `data/processed/` has 5 artifacts and **0 manifests**; mtimes are 2026-10-22.
  `clause_classifier.csv` header is `text,category,source` (no `doc_id`/`split` columns).
- `scripts/verify_provenance.py` → 5 failures, 0 skipped.
- `tests/test_no_leakage.py` → 7 failed, 16 passed
  (T1a/T1b/T2a/T2b/T3a/T3b/T8).
- `data/processed.staging/` holds newer artifacts from 2026-10-26 (code revision `cbd9c29`)
  with the correct `doc_id`/`split` header and all 5 manifests. It was **not** swapped.
- Clean rebuild at HEAD produces the correct schema, 5 manifests, 0 verifier failures, and
  129/129 passing tests. Conclusion: **stale main-tree generated artifacts**, not a code
  regression or test-isolation defect. No code/test fix was made; the guards correctly fail closed.
- The main-tree artifacts were not rebuilt or replaced. That remains approval-gated.

## Fixed this session
- D1–D8 (fresh-clone blockers, T1b, liability/stamp/TDS/S124 severity + scoring, cross-reference notes).
- D9 (obligations): calendar-date deadlines now populate `deadline_date`; passive voice uses the by-agent as obligor (or None when no agent) instead of inventing the grammatical object; written-out numbers normalize to digits.

## Fixed this pass (obligations + ML wording)
- D10: obligations carry zero-based half-open source offsets; `Obligation.text` is the exact
  `clause_text[start:end]` slice. Repeated/ambiguous sentences leave both offsets `None` rather
  than guessing.
- D11: leading/mid/trailing conditions and exceptions are preserved in `condition`; the main-clause
  modal is preferred over a protasis modal; deadlines inside a condition are not attributed to the
  duty; passive by-agents are recovered without inventing a subject.
- D12: beneficiary/counterparty extraction is conservative (explicit `to X` / dative patterns only,
  role nouns or corporate/proper names); optional `party_aliases` canonicalises defined names.
  Ambiguous recipients (`to Mumbai`, `comply with the Act`) stay `None`.
- D13: `ML_RISK_001` no longer presents `predict_proba` as calibrated confidence. The flag is named
  "Model-suggested …" and the explanation says "uncalibrated model score … (raw classifier output,
  not a calibrated probability)".
- D14: `RISK_S124_001` was contract-level but scanned the whole contract, so an unrelated
  "breach of contract" mention suppressed it. It now evaluates only indemnification clauses,
  keeps `evidence_status="unverified"`, and reports an indemnity-specific `search_scope`.
  Regression: `test_s124_not_suppressed_by_unrelated_breach_of_contract_language`.
- Regression coverage added in `tests/test_obligation_extraction.py` (18 cases: offsets, duplicates,
  beneficiary, aliases, conditions/exceptions, protasis, passive, condition dates, written-out
  deadlines) and `tests/test_risk_model.py` (wording/no-"confidence" assertion). The deleted tail of
  `test_tfidf_outputs_are_canonicalised` is restored to match HEAD.

Verification: focused suite (obligations, regressions, risk rules, risk model, P4) → 75 passed;
`uv run ruff check .` → clean. Full main-tree `uv run pytest --tb=no` → 137 passed, 7 failed, all
in `tests/test_no_leakage.py` from stale main-tree `data/processed/` artifacts (missing manifests /
old schema without `doc_id`/`split`). The isolated clean rebuild at HEAD passes 129/129.

## Main-tree provenance failures — VERIFIED stale artifacts (not code defects)
Main tree `data/processed/` has 5 artifacts, **0 manifests**, and an old header without
`doc_id`/`split`; `verify_provenance.py` reports 5 "manifest missing" failures (7 test failures
with lineage). The isolated worktree at `97f4c21` regenerates 5 manifests, passes the verifier
with 0 failures, and passes all 129 tests. Resolution is a separately-approved main-tree artifact
rebuild; do not swap staging blindly or weaken the guards.

## Open (documented, not defects)
- ML risk classifier score is still uncalibrated (`ML_RISK_001`); only its presentation is fixed.
- Whole-contract cross-reference reasoning is not consumed by risk rules (P4); prior suppression
  was reverted as unsafe.
- P3 four-way missing-protection status (`present | incomplete | not_found_in_scope | undetermined`)
  is represented only implicitly by existing `RiskFlag` fields; no explicit status enum or consumer.
  Section 124 now has the "Verify" qualifier and an indemnity-only search scope.
- No-comma leading conditions (e.g. "If required by law the Provider shall …") cannot be split
  reliably without a parser; the responsible party is left `None` rather than guessed.
- The uncommitted user P4 work (analyzer `related_clause_texts` enrichment, `app/utils/text.py`
  markdown headings, P4 tests, reports) is preserved in the working tree and complements the
  committed cross-reference analysis.

## Next actions
1. (Approval-gated) rebuild/replace stale main-tree `data/processed/` artifacts with
   `uv run python scripts/build_training_data.py`, then require
   `verify_provenance.py` 0 failures and a full 144-test main-tree run.
2. Calibrate or label the ML risk score (a raw `predict_proba` remains uncalibrated).
3. Whole-contract cross-reference reasoning consumed by rules, with labelled evaluation.
4. Optional: explicit P3 status enum/consumer if the API needs machine-readable status values.

## Blocks
- Main-tree `data/processed/` remains stale, so the 7 provenance tests stay red until an
  approval-gated rebuild. This is a data-state issue, not a code fix.
- Direct `uvicorn` smoke is blocked by `dcg`; `tests/test_api_smoke.py` covers the API roundtrip.
- Do not push without separate instruction.

---

## Kiro session 2026-10-30 (HEAD 42c25b0 -> b35da18)

State: branch `main`; HEAD advanced from `42c25b0` to `b35da18` (2 local commits,
nothing pushed; `origin/main` at `42c25b0`). Working tree clean. The previously
"uncommitted user P4 work" is committed at `42c25b0`.

Commits this session:
- `85011e2` test(eval): add deterministic synthetic evaluation harness and labelled corpus
- `b35da18` fix(risk): parse written/parenthetical renewal notice periods

Verification at `b35da18` (all via `uv run --no-sync`):
- `ruff check .` -> All checks passed.
- `pytest --tb=no` -> 146 passed, 7 failed (153 collected). The 7 failures are the
  same `tests/test_no_leakage.py` provenance guards on the stale main-tree
  `data/processed/` (Oct 22, no manifests). Unchanged data-state issue; guards
  working as designed.
- Focused suite (obligations, regressions, risk model/rules, P4, eval harness) -> 84 passed.
- `scripts/run_evaluation.py` -> 14/17 cases pass, 3 known limitations, 0 regressions;
  3/3 evidence-integrity invariants hold; exit 0.
- `scripts/run_demo.py` -> exit 0; 12 clauses, 13 obligations, score 100.0/critical.

Added: `nlp/evaluation/` (cases + harness), `scripts/run_evaluation.py`,
`tests/test_evaluation_harness.py`, `reports/evaluations/synthetic_eval_results.{md,json}`,
shared number helpers in `app/utils/text.py`, renewal-notice parsing fix in
`nlp/risk_scoring/rules.py`, defect D12, and `reports/recovery/KIRO_HANDOFF.md`.
Final report updated to the current counts and the new harness.

Not done (approval-gated / documented): main-tree `data/processed/` rebuild;
ML calibration; cross-reference suppression; stamp/TDS and passive-voice recall
(documented as eval known limitations). No push; no co-author trailer.

---

## Kiro session 2026-10-30, second pass (HEAD b35da18 -> NEWCOMMIT)

State: branch `main`; HEAD advanced from `b35da18` to `NEWCOMMIT` (1 local commit,
nothing pushed). Working tree clean after the commit.

Commits this session:
- `NEWCOMMIT` fix(ner): detect stamped-paper and deduction-at-source wording for stamp/TDS

Task: resolve the `stamp_tds_present_missed` evaluation known limitation
(`RISK_STAMP_001` / `RISK_TDS_001` false "not found" prompts on present language).

Root cause: `detect_stamp_duty_mention` / `detect_tds_mention` in `nlp/ner/ner.py`
matched only literal keywords ("stamp duty", "e-stamp", "franking",
"indian stamp act") and `\b(?:tax deducted at source|tds|section 19[45])\b`, so
"duly stamped paper" and "deduction of tax at source" were missed. Reproduced with
a direct detector call (both returned False) and via the eval case before the fix.

Fix (minimal, detector-level only):
- `_STAMP_DUTY_RE` adds tight stamped-wording forms: adverb-qualified "stamped"
  ("duly", "non-judicial", "properly", "sufficiently", "adequately",
  "appropriately"), "stamped paper/certificate/document/instrument/agreement/copy",
  "stamp paper(s)", "stamping of this/the/such". Existing keyword list unchanged.
- `_TDS_RE` keeps the old forms verbatim and adds "tax deduction at source",
  "deduct(ed|ing|ion)? (of)? tax at source", and "deduct(ed|ing)? at source".
  Bare "tax" or "deduction" never matches; the at-source construction is required.
- Jurisdiction gating, payment-clause scoping, severity, "not found — verify"
  wording, evidence status, and search scope in `rules.py` are untouched; a
  detected mention suppresses the review prompt, it is not asserted to be a
  confirmed legal compliance fact.

Regression coverage (tests/test_regressions.py, 4 new tests):
- positives: "duly stamped paper", "non-judicial stamp paper", "stamped copies",
  "stamping of this Agreement", "deduction of tax at source", "deduct tax at
  source", "deduct at source", "amounts deducted at source".
- negative controls: "rubber-stamped the decision", "postage stamp", "date stamp",
  "stamp out fraud", "timestamped", "paper copy", "stamp of approval"; "goods and
  services tax", "income tax returns", "sales tax", "deduction of damages",
  "deduction for late delivery", "source code escrow", "tax deducted from the
  invoice" (no "at source" — intentionally not matched).

Verification at `NEWCOMMIT` (all via `uv run --no-sync`):
- `ruff check .` -> All checks passed.
- `pytest --tb=no -q` -> 157 collected, **150 passed, 7 failed** (junit-verified).
  The 7 failures are the same `tests/test_no_leakage.py` provenance guards on the
  stale main-tree `data/processed/` — unchanged data-state issue, kept separate
  from this task; artifacts not touched.
- Focused suite (obligations, regressions, risk model/rules, P4 adversarial/
  context/cross-reference, eval harness) -> **88 passed** (was 84; +4 new tests).
- `scripts/run_evaluation.py` -> **15/17 pass, 2 known limitations, 0 regressions,
  0 resolved pending**, 3/3 invariants OK, exit 0. Before the fix: 14/17 pass,
  3 known limitations. `stamp_tds_present_missed` now passes; its
  `known_limitation` note was removed and the lock set in
  `tests/test_evaluation_harness.py` updated (otherwise the lock test correctly
  fails on a silently resolved limitation).
- `scripts/run_demo.py` -> exit 0; output identical to the pre-fix baseline
  (12 clauses, 13 obligations, score 100.0/critical; sample MSA still
  stamp_duty_mentioned=false, tds_mentioned=false).

Reports updated: `reports/evaluations/synthetic_eval_results.{md,json}`
(regenerated), final project report (counts + defect D13), `KIRO_HANDOFF.md`.

Not done (approval-gated / documented): main-tree `data/processed/` rebuild;
ML calibration; cross-reference suppression; `obligation_passive` recall. No push;
no co-author trailer.
