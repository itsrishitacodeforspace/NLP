# Final Integration Report — 2026-10-27

## Verified changes (across sessions)
- `app/utils/text.py`: Markdown heading support in `_SECTION_HEADING_RE`.
- `nlp/obligation_extraction/extractor.py`: written-out + parenthetical deadline capture.
- `tests/test_regressions.py`: 2 new regression tests.

## Verification
- Ruff: All checks passed! (project source, excluding .ua/)
- Full suite: 7 failed, 76 passed, 4 warnings (83 collected)

## Remaining failures
- 7 provenance guards (T1a, T1b, T2a, T2b, T3a, T3b, T8) — expected on unswapped production artifacts.

## Production data/models
- Untouched. No swap, retrain, or extraction performed.

## Git status
- HEAD: a1b42986561b7212a9ed9778147158115ffd5c7c, branch main. No commits or pushes.

## Highest-value next action
- P4: consume P1 context bundle in liability/renewal rules to suppress RISK_LIABILITY_002 false positives when a cap exists in a referenced clause, with synthetic-contract regression tests. Requires RiskRule contract change (approval).