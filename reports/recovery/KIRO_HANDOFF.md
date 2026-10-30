# Kiro Handoff — BharatContract AI

Durable session handoff. Preserves (does not replace) the CommandCode records
under `.commandcode/` and the earlier `reports/recovery/` documents. Read
`.commandcode/BHARATCONTRACT_PROJECT_MEMORY.md` and `RECOVERY_TRACKER.md` first
for the full prior history.

Last updated: 2026-10-30 (Kiro session, third pass).

## 1. Verified repository state

- Branch: `main`.
- Starting HEAD this session: `a1aaf8b` (plus a pre-existing uncommitted merge of
  `origin/main` `5a03a1b`, reconciled as `ece750f` — see Section 2).
- Ending HEAD this session: `8c60ae6` + a docs commit on top (4 local commits
  ahead of `origin/main` at `5a03a1b`; branch fast-forwards on push).
  **Nothing pushed.** Remote: `origin` (GitHub).
- Working tree: clean after the commits below (plus repo-local `tmp/` scratch,
  which is gitignored).
- Python: uv-managed 3.12.14; always use `uv run` (host `python` is out of range).

Note: several earlier recovery docs cite baseline `97f4c21`; the actual HEAD has
since advanced through `0ff131e` and `42c25b0`. The previously "uncommitted user
P4 work" is now committed at `42c25b0`, and the main working tree is clean.

## 2. Commits added this session

- `85011e2` test(eval): add deterministic synthetic evaluation harness and labelled corpus
- `b35da18` fix(risk): parse written/parenthetical renewal notice periods
- `aaa9fd5` fix(ner): detect stamped-paper and deduction-at-source wording for stamp/TDS
- `ece750f` merge: reconcile origin/main (5a03a1b) with local stamp/TDS commits.
  `5a03a1b` was the first version of the stamp/TDS fix, pushed before the local
  commit was rewritten into `aaa9fd5` + `a1aaf8b`; the only differences were the
  literal `NEWCOMMIT` hash placeholder in 11 doc lines. The session started with
  that merge in progress and 3 conflicted docs; resolving by keeping the local
  side made the merge tree identical to `a1aaf8b` (no content lost).
- `8c60ae6` fix(risk): suppress missing-cap finding only for resolved, applicable cross-referenced caps

## 3. Key architectural decisions (unchanged, reaffirmed)

- Rule-first, evidence-bound risk engine; ML is a recall booster only and never
  overrides a rule. Model findings are always `evidence_status="unverified"`.
- Graceful degradation is mandatory: Neo4j/Postgres/OCR/transformers all no-op.
- Single taxonomy source (`nlp/taxonomy.py`). Timestamps via `app.core.time.utcnow()`.
- Provenance ≠ evaluation ≠ predictive validity. A manifest proves lineage only.
- Cross-reference context is advisory; a reference or keyword match never suppresses
  a finding (the earlier keyword suppression was reverted as unsafe — see
  `reports/evaluations/p4_adversarial_review_20261027.md`).
- No production artifact replacement, retraining, archive extraction, service
  startup, or push without explicit approval. `data/processed/` is never overwritten
  without approval; `data/processed.staging/` stays distinct.

## 4. What this session added

- `nlp/evaluation/` — 17 synthetic labelled cases (`cases.py`) + runner (`harness.py`)
  covering risk true/false positives, severity calibration, uncertain legal
  conclusions, conditions/exceptions, party/beneficiary ambiguity, cross-reference
  resolution, passive voice, and a detection-recall gap. Three evidence-integrity
  invariants are checked across every finding.
- `scripts/run_evaluation.py` — writes `reports/evaluations/synthetic_eval_results.{md,json}`;
  fail-closed (exit 1) on unexpected regressions or invariant violations.
- `tests/test_evaluation_harness.py` — locks results: fails on a new regression
  **and** on a silently resolved known limitation.
- `app/utils/text.py` — shared `written_number_to_int` + `NUMBER_TOKEN_RE`.
- `nlp/risk_scoring/rules.py` — `rule_auto_renewal` now parses digit, written
  ("ninety") and parenthetical ("sixty (60)") in-clause notice periods, so a clearly
  stated notice reduces severity from high to medium. Cross-clause notices remain
  advisory-only (P4 adversarial tests unchanged).
- `nlp/ner/ner.py` — `detect_stamp_duty_mention` / `detect_tds_mention` now also match
  tight stamped-wording ("duly stamped", "non-judicial stamp paper", "stamped
  copies", "stamping of this Agreement") and at-source constructions ("deduction of
  tax at source", "deduct(ed|ing) at source"). Negative controls: "rubber-stamped",
  "postage stamp", "timestamp", and unrelated tax/deduction mentions do not match.
  Indian-jurisdiction gating, payment-clause scoping, and the "not found — verify"
  framing of `RISK_STAMP_001`/`RISK_TDS_001` are unchanged.
- `tests/test_regressions.py` — 4 new detector tests (positive wording + negative
  controls for both detectors).
- Eval case `stamp_tds_present_missed` no longer declares a known limitation; the
  lock set in `tests/test_evaluation_harness.py` now expects only the two remaining
  limitations.
- `nlp/risk_scoring/rules.py` — `rule_uncapped_liability` now consults the
  resolver's cross-reference context before raising `RISK_LIABILITY_002`.
  Suppression requires an explicit reference with `status == "resolved"` AND
  referenced text stating a cap that verifiably covers the assessed liability
  (mutual or matching party scope, no exclusions, no loss-category mismatch).
  Unresolved/missing/ambiguous references, related text without a resolved
  reference (keyword suppression stays reverted), exclusions, conflicts, and
  unknown party scope all keep the finding as a human-review prompt.
- `tests/test_p4_cap_resolution.py` — 14 new tests (valid/invalid/unrelated/
  ambiguous/excluded caps, negative controls). One P4 cross-reference test was
  updated to the new contract: its scenario now uses an excluding cap so the
  advisory-note assertions still hold.
- Eval case `liability_cap_in_crossref` no longer declares a known limitation;
  the lock set now expects only `obligation_passive`.

## 5. Reproducible setup and verification commands

```bash
uv sync --extra dev
uv run ruff check .
uv run pytest --tb=no
uv run pytest tests/test_evaluation_harness.py tests/test_risk_rules.py -q
uv run python scripts/run_demo.py
uv run python scripts/run_evaluation.py
uv run python scripts/verify_provenance.py
```

## 6. Current results (verified at `8c60ae6`)

- `ruff check .` → All checks passed.
- Full suite → **164 passed, 7 failed** (171 collected). The 7 failures are all in
  `tests/test_no_leakage.py` (T1a/T1b/T2a/T2b/T3a/T3b/T8) — unchanged stale
  `data/processed/` provenance guards.
- Focused suite (obligations, regressions, risk model/rules, P4 incl. cap
  resolution, eval harness) → **102 passed**.
- `scripts/run_evaluation.py` → **16/17 cases pass, 1 known limitation, 0 regressions**;
  3/3 evidence-integrity invariants hold; exit 0. Progression: 14/17 (3 known
  limitations) → 15/17 (stamp/TDS fix) → 16/17 (cross-reference cap fix);
  `obligation_passive` is the only remaining known limitation.
- `scripts/run_demo.py` → exit 0; 12 clauses, 13 obligations, score 100.0/critical;
  output identical to the pre-fix baseline.
- `scripts/verify_provenance.py` → 5 failures (missing manifests on the stale
  main-tree `data/processed/`). Approval-gated rebuild, not performed.

## 7. Outstanding defects / known limitations

1. **7 provenance test failures** — stale main-tree `data/processed/` (Oct 22, old
   `text,category,source` header, 0 manifests). Data-state issue, not a code defect.
   Resolution is an approval-gated rebuild: `uv run python scripts/build_training_data.py`
   then require `verify_provenance.py` 0 failures. Do **not** swap staging blindly or
   weaken the guards.
2. **`obligation_passive`** (eval known limitation) — hyphenated written compounds
   ("twenty-four") not normalised by the deadline parser; passive by-agent not
   recovered in this construction.
3. ML risk score remains uncalibrated (presentation only is fixed).
4. P3 four-way missing-protection status has no explicit enum/consumer
   (see `reports/recovery/P3_STATUS_DESIGN.md`).
5. TDS detection still requires the at-source construction: "tax deducted from the
   invoice" (no "at source") is intentionally not matched, so `RISK_TDS_001` may
   still fire on contracts that address withholding in other words. This is a
   deliberate precision-over-recall choice, documented in `tests/test_regressions.py`.
6. Cross-reference cap suppression is intentionally narrow: a cap whose party
   scope cannot be determined from the text ("Total liability shall not exceed
   ...") does NOT suppress, so genuine caps phrased without party language still
   produce a review prompt. Caps with carve-outs also keep the finding by design.
7. Renewal notices in cross-referenced clauses remain advisory-only; the same
   conservative contract used for caps has not been applied to
   `RISK_RENEWAL_001`.

## 8. Next three prioritised actions

1. **Obligation deadline + passive fix:** reuse `written_number_to_int` /
   `NUMBER_TOKEN_RE` in the obligation extractor for hyphenated compounds, and recover
   the passive by-agent for "shall be <verb-ed> by <party>"; resolve `obligation_passive`.
2. **Approval-gated `data/processed/` rebuild** to clear the 7 provenance failures,
   with a full post-rebuild suite run recorded. Ask before running.
3. **Renewal cross-reference notice** under the same fail-closed contract used
   for caps (resolved reference + verified opt-out right in the target clause),
   or **P3 status enum** if the API needs machine-readable missing-protection
   status.

## 9. Continuation prompt for a future Kiro session

> Resume BharatContract AI from `reports/recovery/KIRO_HANDOFF.md` at HEAD `8c60ae6`
> (+docs) on branch `main`. Verify with `uv run ruff check .` and
> `uv run pytest --tb=no` (expect 164 passed, 7 provenance failures from stale
> `data/processed/`), then `uv run python scripts/run_evaluation.py` (expect
> 16/17, 1 known limitation: `obligation_passive`). Pick the next action from
> Section 8, work test-first in a verified milestone, keep the evaluation lock
> list honest, do not weaken provenance guards, do not rebuild/replace
> `data/processed/` or push without explicit approval, and do not add a
> co-author trailer.

No secrets, tokens, or credentials are stored in this handoff.
