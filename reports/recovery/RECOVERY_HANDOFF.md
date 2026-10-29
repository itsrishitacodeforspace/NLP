# Recovery Handoff

## Resume from
- Branch `main`; verification baseline `97f4c21` (14 commits ahead of `origin/main`
  `a1b4298`). This handoff update follows that baseline. Do not push unless separately instructed.
- Final college report is at `reports/BHARATCONTRACT_AI_FINAL_PROJECT_REPORT.md`.
- Read `reports/recovery/RECOVERY_TRACKER.md` and `DEFECT_REGISTER.md` first.
- Clean verification at `97f4c21`: repo-local worktree `tmp/bcc-clean-97f4c21`
  regenerated 5 manifests, `verify_provenance.py` 0 failures, all 129 tests passed.
- Main `data/processed/` remains the stale 2026-10-22 artifact set (0 manifests, old
  `text,category,source` header); its 7 provenance failures are a data-state issue.

## Do not break
- Preserve the uncommitted user work in the main tree: P4 `related_clause_texts` enrichment in
  `app/services/analyzer.py`, `app/utils/text.py` markdown headings, the two new tests in
  `tests/test_regressions.py`, `tests/test_p4_*.py`, `reports/evaluations/`, `docs/`, and the
  `command-code-session*` files. The pass commit intentionally excludes these; do not overwrite them.
- Do not weaken/skip tests (especially T1b and the provenance guards).
- Do not swap `data/processed.staging/` into `data/processed/` or retrain models.
- Do not add a co-author trailer to commits.

## Highest-value next work
1. (Approval-gated) Regenerate the main-tree `data/processed/` artifacts with
   `uv run python scripts/build_training_data.py`; require `verify_provenance.py` 0 failures and
   a full 144-test run. Do not swap staging blindly or weaken provenance guards.
2. Calibrate or label the ML risk score (`ML_RISK_001`); raw `predict_proba` remains uncalibrated.
3. P2 risk correctness: RISK_LIABILITY_002 / RISK_RENEWAL_001 false positives when a cap/notice exists in a cross-referenced clause. Requires whole-contract reasoning; the prior keyword-suppression attempt was reverted as unsafe (see `reports/evaluations/p4_adversarial_review_20261027.md`).
4. A small labelled evaluation corpus (cross-refs that do/do not change meaning, definitions, exceptions, precedence, schedule-located protections, broken/circular refs) to measure any change.
5. Optional: explicit P3 status enum/consumer for `present | incomplete | not_found_in_scope | undetermined`.

## Environment reminders
- Always `uv run` (host Python is 3.13, out of range).
- `data/processed/` is generated (not shipped); regenerate with `build_training_data.py`.
- Use repo-local `tmp/` for scratch/worktrees; do not use the system temp directory.
- Clean worktree: `tmp/bcc-clean-97f4c21` (detached at `97f4c21`, gitignored).
