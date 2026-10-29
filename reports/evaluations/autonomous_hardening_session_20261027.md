# Autonomous Hardening Session — 2026-10-27

## A. Initial state

- **Branch:** `main`, HEAD `a1b42986561b7212a9ed9778147158115ffd5c7c` (origin/main).
- **Initial worktree:** 17 modified tracked files + 17 untracked files (per project memory). The `.ua/` knowledge-graph artifacts and `docs/UA_ONBOARDING.md` were generated in a prior session and are untracked.
- **Baseline (verified this session):** `uv run --no-sync ruff check . --exclude .ua` → All checks passed! (project source clean). `uv run --no-sync pytest` → **7 failed, 76 passed, 4 warnings in 46.59s** (81 collected after this session's +2 tests; originally 81 collected / 74 passed / 7 failed). The 7 failures are the expected provenance guards (`T1a, T1b, T2a, T2b, T3a, T3b, T8`) on unswapped, unlineaged production artifacts. They were preserved, not suppressed.

## B. Findings

1. **Obligation deadline regex was digit-only** (`nlp/obligation_extraction/extractor.py`, `DEADLINE_RE`). Legal phrasing like "within thirty (30) days" was silently dropped because the regex required a leading digit immediately followed by the unit. Root cause: `\d+\s+(?:day|days|...)` could not bridge the parenthetical "(30)".
2. **Segmenter did not recognise Markdown-prefixed headings** (`app/utils/text.py`, `_SECTION_HEADING_RE`). Headings written as `## 7. Limitation of Liability` (common in Markdown contracts) were not detected as section headings, so no section number was attached. Root cause: the regex anchored on a leading digit/Article/Section with no allowance for leading `#` markers (and `#` is a comment char in `re.VERBOSE` mode, requiring `[#]`).
3. **Context resolver** already supported schedule/exhibit headings with leading `#` (`_SCHEDULE_HEAD_RE`); no change needed there.

## C. Changes

| File | Change | Why safe |
|---|---|---|
| `app/utils/text.py` | `_SECTION_HEADING_RE` now allows an optional leading `[#]+` marker and a `Section <Roman>` alternative; compiled with `re.IGNORECASE`. | Additive; existing headings still match; `detect_section_number`/`looks_like_section_heading` consume the same regex. |
| `nlp/obligation_extraction/extractor.py` | `DEADLINE_RE` extended to accept written number words and an optional parenthetical digit before the unit; `_extract_deadline` normalises "(30)" and converts leading word to digits. | Backwards-compatible: prior digit forms still match; only adds new matches and normalises output. |
| `tests/test_regressions.py` | Added `test_obligation_deadline_parenthetical_digits` and `test_segmenter_markdown_headings`. | Regression guards for the two fixes. |

No production data, model, or artifact was touched. No new dependencies.

## D. Verification

- `uv run --no-sync ruff check app/utils/text.py nlp/obligation_extraction/extractor.py nlp/context/resolver.py` → All checks passed!
- `uv run --no-sync pytest tests/test_regressions.py` → 0 failed (all pass).
- `uv run --no-sync pytest` → **7 failed, 76 passed, 4 warnings** (the 7 are the expected provenance guards; +2 new regression tests over the 74 baseline).
- The 7 provenance failures remain visible and unchanged.

## E. Research integrity

- `data/datasets/`, `data/processed/`, `data/processed.staging/`, `models/*.7z`, `models/*.joblib` were not modified, regenerated, or extracted.
- No retraining, no artifact swap, no service startup.
- Provenance limitations unchanged: production artifacts remain unverified; both model archives `provenance-unverified`.

## F. Next actions

1. **Consume the P1 context bundle in liability/renewal rules** (P4) — needs approval; highest value for TC-05 false positives.
2. **Four-way missing-protection status** (P3) consuming P2's `search_scope` and P1's `related_clause_ids`.
3. **Evaluation harness** with synthetic labelled corpus (cross-refs, definitions, exceptions, precedence, schedule-located protections, broken/circular refs).

Prohibited/deferred: production artifact swap, model retraining, P5–P7 implementation, fixing/hiding the 7 provenance failures, service startup, Git staging/commit/push.