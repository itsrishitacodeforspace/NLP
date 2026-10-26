# BharatContract AI — Next Session Restart

Short operational checklist. Read `BHARATCONTRACT_PROJECT_MEMORY.md` first.

## 0. Do not break this
- **Do not** swap `data/processed.staging/` into `data/processed/`.
- **Do not** retrain models or extract `.7z` archives.
- **Do not** fix/hide the **7** provenance test failures (they are expected while artifacts are unswapped).
- **Do not** stage/commit/push. Preserve all untracked files (`.commandcode/`, the two handoff `.md` files,
  `reports/`, `nlp/context/`, provenance modules, `tests/test_{no_leakage,context_resolution,evidence_binding}.py`).
- **Do not** start services or regenerate datasets as part of a code task.

## 1. Orient (2 minutes)
```bash
git status --short --branch          # expect 17 modified + 17 untracked
git log --oneline -3                 # expect cbd9c29 at HEAD
uv run ruff check .                  # expect clean
uv run pytest -q                     # expect 81 collected / 74 passed / 7 failed
```
If the counts differ from 81/74/7, **stop** and record the discrepancy before doing anything else.

## 2. Read, in order
1. `.commandcode/BHARATCONTRACT_PROJECT_MEMORY.md`
2. `reports/evaluations/generalizable_analysis_audit.md` (ranked root causes R1–R9)
3. `reports/evaluations/p1_context_resolution_report.md`
4. `reports/evaluations/p2_evidence_binding_report.md`
5. `BharatContract_AI_Agent_Master_Prompt.md` + `BharatContract_AI_Project_Charter.md` (operating rules)

## 3. Then, in priority order — **ask for approval before each**

1. **Review P1 + P2 diffs** (unreviewed by the user): `nlp/context/`, `_bind_evidence` in
   `nlp/risk_scoring/rules.py`, the five `RiskFlag` fields, and the two new test modules. Confirm no rule
   trigger/severity changed.
2. **P3 (if approved):** four-way missing-protection status
   (`present | incomplete | not_found_in_scope | undetermined`) consuming P2's `search_scope` and P1's
   `related_clause_ids`. Must not equate "not found" with illegality.
3. **P4 (if approved):** consume the P1 context bundle in the liability/renewal rules — the TC-05 false
   positives (`RISK_LIABILITY_002`, `RISK_RENEWAL_001`) are the first targets, but **test generally**, not
   against TC-05 alone.
4. **Evaluation harness (if approved):** build the small labelled corpus described in the audit §7
   (cross-references that do/do not change meaning, definitions, exceptions, precedence, schedule-located
   protections, broken/circular refs, synonym-drafted protections, true/false missing-protection cases).
   Record label provenance as *synthetic* where applicable.
5. **Later:** P5 (ML separation/measurement), P6 (obligation fields), P7 (legal grounding).
6. **Only much later, with explicit approval:** production swap (requires durable backup re-confirmation +
   an accepted behavioural diff) and model retraining (separate gate).

## 4. Known quick wins if asked
- `classifier_ml.py` is dead code (never imported).
- `user_role` is accepted by API/analyzer but unused; `playbook_id`, `use_rule_based_classifier`,
  `enable_background_jobs`, `default_jurisdiction` are dead config.
- `plan.md` still says "phases complete" alongside an unchecked provenance limitation → docs cleanup.
- Segmenter ignores Markdown-prefixed headings (`## 7. LIABILITY`) → no section numbers for such files.

## 5. Environment reminders
- Always `uv run …` (host `python` is 3.13.x, outside the project's declared range).
- No `.env` needed. Auth off by default. Neo4j/Postgres absent → in-memory fallbacks.
- OCR (`tesseract`) and transformers (torch/transformers + DeBERTa weights) are **absent** → those paths are inert.

## 6. Reporting contract (the user expects this)
- State the exact commands and exit codes you actually ran.
- Separate **code correctness** from **production readiness**.
- Report every failure, including the seven expected ones; never skip/xfail to go green.
- Never claim legal correctness from keyword matches or unverified citations.
- A manifest is lineage evidence only — never accuracy.
