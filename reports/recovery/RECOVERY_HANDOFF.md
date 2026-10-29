# Recovery Handoff

## Resume from
- Branch `main`, HEAD `118e8ae` plus the single local pass commit (10 commits ahead of
  `origin/main` `a1b4298`). Do not push unless separately instructed.
- Read `reports/recovery/RECOVERY_TRACKER.md` and `DEFECT_REGISTER.md` first.

## Do not break
- Preserve the uncommitted user work in the main tree: P4 `related_clause_texts` enrichment in
  `app/services/analyzer.py`, `app/utils/text.py` markdown headings, the two new tests in
  `tests/test_regressions.py`, `tests/test_p4_*.py`, `reports/evaluations/`, `docs/`, and the
  `command-code-session*` files. The pass commit intentionally excludes these; do not overwrite them.
- Do not weaken/skip tests (especially T1b and the provenance guards).
- Do not swap `data/processed.staging/` into `data/processed/` or retrain models.
- Do not add a co-author trailer to commits.

## Highest-value next work
1. P2 risk correctness: RISK_LIABILITY_002 / RISK_RENEWAL_001 false positives when a cap/notice exists in a cross-referenced clause. Requires whole-contract reasoning; the prior keyword-suppression attempt was reverted as unsafe (see `reports/evaluations/p4_adversarial_review_20261027.md`).
2. P3 four-way missing-protection status (`present | incomplete | not_found_in_scope | undetermined`) consuming P1/P2 context.
3. A small labelled evaluation corpus (cross-refs that do/do not change meaning, definitions, exceptions, precedence, schedule-located protections, broken/circular refs) to measure any change.

## Environment reminders
- Always `uv run` (host Python is 3.13, out of range).
- `data/processed/` is generated (not shipped); regenerate with `build_training_data.py`.
- Fresh-checkout scratch lives in `tmp/` (gitignored).
