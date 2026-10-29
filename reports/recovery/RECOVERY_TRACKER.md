# Recovery Tracker — BharatContract AI

Last updated: 2026-10-29

## State
- Branch `main`, HEAD `be51191` plus this docs-only update (14 local commits ahead of
  `origin/main` `a1b4298`). Nothing pushed.
- Fresh-checkout validation: git worktree at `tmp/freshcheckout` (gitignored scratch), currently at `118e8ae`.

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

## Verified fresh-checkout workflow (milestone 14)
1. `uv sync --extra dev` → exit 0 (154 packages, Python 3.12.14)
2. `uv run ruff check .` → "All checks passed!"
3. `uv run python scripts/build_training_data.py` → exit 0 (train-only, 5 artifacts + manifests)
4. `uv run python scripts/verify_provenance.py` → 0 failures, 0 skipped
5. `uv run uvicorn app.main:app` → serves; `/healthz` 200, `/docs` 200
6. `uv run pytest -q` → **exit 0** (all pass against regenerated corpus)

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
`uv run ruff check .` → clean. Full `uv run pytest --tb=no` → 137 passed, 7 failures, all in
`tests/test_no_leakage.py` from the known stale main-tree `data/processed/` artifacts
(missing manifests / empty `split` columns), unchanged by this fix.

## Main-tree provenance failures — VERIFIED stale artifacts (not code defects)
Main tree `data/processed/` has 5 artifacts and **0 manifests**; `verify_provenance.py` reports 5 "manifest missing" failures (7 test failures total with lineage). Regenerated fresh checkout passes 0 failures. Resolution is a separately-approved artifact rebuild.

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
1. Calibrate or label the ML risk score (a raw `predict_proba` remains uncalibrated).
2. Whole-contract cross-reference reasoning consumed by rules, with labelled evaluation.
3. (Approval-gated) rebuild/replace stale `data/processed/` artifacts.
4. Optional: explicit P3 status enum/consumer if the API needs machine-readable status values.

## Blocks
- None. Do not push without separate instruction.
