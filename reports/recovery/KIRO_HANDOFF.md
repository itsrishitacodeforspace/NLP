# Kiro Handoff — BharatContract AI

Durable session handoff. Preserves (does not replace) the CommandCode records
under `.commandcode/` and the earlier `reports/recovery/` documents. Read
`.commandcode/BHARATCONTRACT_PROJECT_MEMORY.md` and `RECOVERY_TRACKER.md` first
for the full prior history.

Last updated: 2026-10-30 (Kiro session, second pass).

## 1. Verified repository state

- Branch: `main`.
- Starting HEAD this session: `b35da18`.
- Ending HEAD this session: `NEWCOMMIT` (3 local commits ahead of `origin/main` at
  `42c25b0`). **Nothing pushed.** Remote: `origin` (GitHub).
- Working tree: clean after the commit below (plus repo-local `tmp/` scratch,
  which is gitignored).
- Python: uv-managed 3.12.14; always use `uv run` (host `python` is out of range).

Note: several earlier recovery docs cite baseline `97f4c21`; the actual HEAD has
since advanced through `0ff131e` and `42c25b0`. The previously "uncommitted user
P4 work" is now committed at `42c25b0`, and the main working tree is clean.

## 2. Commits added this session

- `85011e2` test(eval): add deterministic synthetic evaluation harness and labelled corpus
- `b35da18` fix(risk): parse written/parenthetical renewal notice periods
- `NEWCOMMIT` fix(ner): detect stamped-paper and deduction-at-source wording for stamp/TDS

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

## 6. Current results (verified at `NEWCOMMIT`)

- `ruff check .` → All checks passed.
- Full suite → **150 passed, 7 failed** (157 collected). The 7 failures are all in
  `tests/test_no_leakage.py` (T1a/T1b/T2a/T2b/T3a/T3b/T8) — unchanged stale
  `data/processed/` provenance guards.
- Focused suite (obligations, regressions, risk model/rules, P4, eval harness) → **88 passed**.
- `scripts/run_evaluation.py` → **15/17 cases pass, 2 known limitations, 0 regressions**;
  3/3 evidence-integrity invariants hold; exit 0. Before this fix: 14/17 pass,
  3 known limitations; `stamp_tds_present_missed` was the resolved one.
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
2. **`liability_cap_in_crossref`** (eval known limitation) — a cap in a referenced
   clause still yields a false `RISK_LIABILITY_002`; needs conservative whole-contract
   reasoning, not keyword suppression.
3. **`obligation_passive`** (eval known limitation) — hyphenated written compounds
   ("twenty-four") not normalised by the deadline parser; passive by-agent not
   recovered in this construction.
4. ML risk score remains uncalibrated (presentation only is fixed).
5. P3 four-way missing-protection status has no explicit enum/consumer
   (see `reports/recovery/P3_STATUS_DESIGN.md`).
6. TDS detection still requires the at-source construction: "tax deducted from the
   invoice" (no "at source") is intentionally not matched, so `RISK_TDS_001` may
   still fire on contracts that address withholding in other words. This is a
   deliberate precision-over-recall choice, documented in `tests/test_regressions.py`.

## 8. Next three prioritised actions

1. **Obligation deadline + passive fix:** reuse `written_number_to_int` /
   `NUMBER_TOKEN_RE` in the obligation extractor for hyphenated compounds, and recover
   the passive by-agent for "shall be <verb-ed> by <party>"; resolve `obligation_passive`.
2. **Approval-gated `data/processed/` rebuild** to clear the 7 provenance failures,
   with a full post-rebuild suite run recorded. Ask before running.
3. **Cross-reference suppression for liability caps** (`liability_cap_in_crossref`)
   under a narrow, conservative rule contract — never keyword suppression.

## 9. Continuation prompt for a future Kiro session

> Resume BharatContract AI from `reports/recovery/KIRO_HANDOFF.md` at HEAD `NEWCOMMIT`
> on branch `main`. Verify with `uv run ruff check .` and `uv run pytest --tb=no`
> (expect 150 passed, 7 provenance failures from stale `data/processed/`), then
> `uv run python scripts/run_evaluation.py` (expect 15/17, 2 known limitations).
> Pick the next action from Section 8, work test-first in a verified milestone,
> keep the evaluation lock list honest, do not weaken provenance guards, do not
> rebuild/replace `data/processed/` or push without explicit approval, and do not
> add a co-author trailer.

No secrets, tokens, or credentials are stored in this handoff.
