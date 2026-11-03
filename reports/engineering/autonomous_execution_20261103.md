# Autonomous Execution Session Report — 2026-11-03

**Date:** November 3, 2026
**Agent:** Main Engineering Agent (integration) + 5 parallel workstream subagents
**Charter:** `BharatContract_AI_Project_Charter.md` (evidence discipline §7, reporting standard §19, no-push §9)
**Predecessor report:** the file previously at this path was a stale Phase 2B session report (HEAD `93cedd9`, 262 tests). It was **preserved**, not overwritten, at `reports/engineering/autonomous_execution_phase2b_20261102.md` (rename committed).

---

## 1. Initial and Final HEAD

| | Value |
|---|---|
| Initial HEAD at session start | `f0bad0aeabe6254da22ee75456c3053ffc2cd428` (branch `main`, 18 ahead of origin) |
| Final HEAD (all workstream commits landed) | `fc400a680f830927ce3673338f25ae98ca20c103` |
| Final HEAD after this report's commit | see §13 (one additional docs commit on top of `fc400a6`) |

The previous session's seven claimed fix commits (`6251674`, `db45431`, `2ae9ff4`, `4b1a9ca`, `3187c0f`, `6e20252`, `7fbbabe`) plus the audit `be1359f` were **all present and verified in history** at session start; their claimed state (414 passing tests) was independently reproduced before any new work began.

## 2. Branch and Git Status

- Branch: `main` (upstream `origin/main`, merge-base `2ca788f`).
- Ahead of origin: **18 at start → 47 at integration → 48 after this report's commit.**
- Working tree: **clean** throughout the integration pass except:
  - `sync.log` — untracked, **pre-existing** HuggingFace bucket sync log (`/marimo/nlp -> hf://buckets/...`). Not touched, not committed. Preserved per charter.
  - This report (new file) and the rename of the stale Phase 2B report (committed in the docs commit).
- No remote pushes. No destructive operations. No history rewrites.

## 3. Confirmed Work Completed (main-agent verified)

The main agent independently re-ran every baseline and spot-checked the key claims of each workstream (charter zero-trust rule — subagent reports are not taken as proof). Everything below marked ✅ was re-verified by the main agent in this session; items marked (subagent) were verified by the owning workstream with committed regression tests but not re-executed line-by-line by the main agent.

### Baseline reproduction (pre-work)
✅ At `f0bad0a`: `uv run pytest tests/` → **414 passed**; `uv run ruff check .` → 3 pre-existing B008 (all in `scripts/check_evaluation_regression.py`, `typer.Option` in argument defaults — pre-existing style, not introduced this session); `uv run python scripts/verify_provenance.py` → **0 failure(s), 0 skipped**; `uv run python scripts/run_demo.py` → clean run.

### Final verification (post-integration, all re-run by main agent)
✅ `uv run pytest tests/` → **560 passed, 6 warnings, exit 0** (68.9 s). The exit-code anomaly noted by the subagents (560 passed but non-zero exit, attributed to a loguru sink-write race at teardown) **did not reproduce** on a clean run — treated as environment-level, not a defect in the code.
✅ `uv run ruff check .` → still exactly the 3 pre-existing B008 in `scripts/check_evaluation_regression.py` (lines 190/196/202). No new lint findings from any workstream.
✅ `uv run python scripts/verify_provenance.py` → **0 failure(s), 0 skipped**.
✅ `uv run python scripts/run_demo.py` → clean, full JSON summary.
✅ `tests/test_no_stale_duplicates.py` → green: root duplicates (`risk_scoring/`, `obligation_extraction/`, etc.) byte-identical to `nlp/` after all workstream edits.
✅ Targeted security suite re-run: `tests/test_security_hardening.py tests/test_auth.py tests/test_rls.py` → **28 passed**.

### Spot-verification of workstream claims (main agent, live pipeline runs on `data/raw/`)
| Claim | Verification result |
|---|---|
| New rule `RISK_NONCOMPETE_001` fires on post-employment non-compete | ✅ `sample_employment.txt` §5.1 (12-month post-termination restraint) → rule fires |
| New rule `RISK_DISPUTE_001` fires where no dispute mechanism exists | ✅ fires on `sample_employment`, `sample_data_processing`, `sample_consulting`; correctly **absent** on `sample_nda` (which has a court-jurisdiction clause) |
| Enrichment fields populated on rule findings | ✅ `sample_msa.txt`: 9/9 rule findings carry non-None `impact_summary` + `review_action`; `RISK_LIABILITY_001` shows affected party, review action, uncertainty note |
| Score explainability | ✅ `sample_msa.txt`: `risk_score_breakdown` = `{top: 85.0, volume: 18.0, severity_mass: 4.1, cap_adjustment: -7.1, findings_by_severity: {...}}` + permanent `score_caveat` |
| Obligation frequency extraction | ✅ `sample_vsa.txt` → `['monthly', 'quarterly']` |
| All 6 samples: parties ≥ 2, effective date found, ≥ 1 obligation | ✅ all six (note: 2 samples detect a 3rd "party" — entity over-detection, documented limitation §11) |
| ML booster adds only non-redundant findings | (subagent, report committed) 63 `ML_RISK_001` added, **0 redundant** on 300-doc CUAD-train sample; all `source="model"`, `evidence_status="unverified"` |
| Contradiction detector `RISK_CONFLICT_001` | (subagent, report committed) 0 false positives across all 6 `data/raw` samples; conservative (abstains on scope ambiguity) |
| Parser fixtures: 100% offset-slice invariant + page_hint | (subagent, report committed) 5 generated fixtures; 1.8M-char doc parsed+segmented in **0.34 s**, 997/997 clauses slice-exact, 997/997 page_hint correct |

## 4. Subagent Contributions

Five workstreams ran in parallel (Agent 6, the independent reviewer, was folded into the main agent's integration pass above). All committed locally into the shared tree; where commits interleave, git log content is authoritative (one commit, `33a8d15`, absorbed files from a parallel edit — content verified, message attribution noted).

| Workstream | Subagent session | Commits |
|---|---|---|
| Security & backend reliability | `ses_e5e9f506effe4AU3zf1DQ5vTxt` | `357a20a`, `b5ea595`, `e0da7de`, `c268add`, `9c34b24`, `6e0b32b` (+carried in `33a8d15`), `803315d`, `84340a2`, `b95dd17`, `e5539b1` |
| Evaluation science | `ses_e5e9f506dffeN7wg5GTKcQnjHZ` | `5900bc6`, `a95a5c4`, `e36de67`, `e32914c`, `24d6117`, `fc400a6` |
| Indian contract coverage | `ses_e5e9f506cffeervJXZHMC25S0j` | `97a4840`, `30ba884`, `c516cef`, `3d2a1cc` (incl. `4cd5f1b` style fix) |
| Risk & obligation quality | `ses_e5e9f506bffeZoRUWDReJp6YP0` | `3d2a1cc` (schema, shared), `33a8d15`, `cb2dc63`, `c58866d`, `2fdf8fd`, `88b05d8` |
| Parser reliability | `ses_e5e9f506affeDKOVlOm3exrjFh` | `3e22d59`, `3237bdf`, `2e3cf14` |

Workstream reports (committed):
- `reports/security/autonomous_session_20261103.md`
- `reports/evaluations/autonomous_session_20261103_eval.md` (+ 6 evaluation reports below)
- `reports/evaluations/indian_coverage_20261103.md`
- `reports/engineering/risk_quality_20261103.md`
- `reports/engineering/parser_reliability_20261103.md`

## 5. Files Changed

Full diff: `git diff --stat f0bad0a..fc400a6` (29 commits). Highlights:

- **Backend/security:** `app/api/routes_contracts.py` (unique contract_id, true 413), `app/api/deps.py` (JWT re-validation vs live UserStore), `app/api/routes_auth.py` (rate limiting), `app/core/security.py` (secret guard, `has_ever_seen`), `app/main.py` (startup guard), `app/services/jobs.py` (ThreadPoolExecutor bound by `JOB_WORKER_COUNT`), `app/core/config.py` (new setting), `app/models/schemas.py` (additive fields only).
- **NLP:** `nlp/risk_scoring/rules.py` (+`RISK_NONCOMPETE_001`, `RISK_DISPUTE_001`, `RISK_CONFLICT_001`, enrichment population on all rules, `RISK_DATA_MISSING` fix), `nlp/risk_scoring/scorer.py` (breakdown), `nlp/risk_scoring/case_law.py` (statute-only entries, `verify_note` honesty), `nlp/obligation_extraction/extractor.py` (frequency, beneficiary, dedup), `app/services/analyzer.py` (party-detection dead code fix, page_hint forward search), `app/services/parser.py` / `app/services/segmenter.py` / `app/utils/text.py` (header false-positive limit, `_ANNEXURE_HEADING_RE`, OCR hint).
- **Evaluation:** `nlp/evaluation/family_split.py`, `nlp/evaluation/classifier_metrics.py`, `scripts/eval_rules_vs_hybrid.py`, `scripts/eval_heldout.py`, `scripts/generate_parser_reliability_report.py`.
- **Data:** 5 new synthetic Indian samples in `data/raw/` (clearly labeled synthetic; fictional parties/CINs).
- **Tests (new):** `tests/test_security_hardening.py`, `tests/test_indian_contracts.py`, `tests/test_realistic_fixtures.py`, `tests/test_risk_quality.py`, `tests/test_evaluation_family_split.py`, `tests/test_rules_vs_hybrid.py`, `tests/fixtures/build_fixtures.py`.
- **Root duplicates** re-synced to `nlp/` after each edit; drift locked by `tests/test_no_stale_duplicates.py`.

## 6. Tests and Exact Commands

```bash
cd /marimo/nlp
uv run pytest tests/                                            # full suite
uv run pytest tests/test_security_hardening.py tests/test_auth.py tests/test_rls.py   # targeted security
uv run ruff check .
uv run python scripts/verify_provenance.py
uv run python scripts/run_demo.py
uv run pytest tests/test_indian_contracts.py                    # Indian scenario regression lock
uv run pytest tests/test_realistic_fixtures.py                  # parser fixture suite
```

## 7. Actual Pass/Fail/Skip Counts

| Run | Result |
|---|---|
| Baseline at `f0bad0a` (pre-work) | **414 passed** |
| Final full suite | **560 passed, 0 failed, 0 skipped**, 6 warnings (deprecation only), exit 0 |
| Targeted security suite (re-verified) | **28 passed** |
| New tests added this session | **146** (560 − 414), spanning the 7 new test files above |

## 8. Ruff and Provenance Results

- **Ruff:** `uv run ruff check .` → 3 errors, all pre-existing B008 in `scripts/check_evaluation_regression.py` (typer.Option in argument defaults). No findings introduced by any workstream. `uv run ruff check app/ tests/` → clean.
- **Provenance:** `uv run python scripts/verify_provenance.py` → `0 failure(s), 0 skipped`. All processed artifacts verify against their manifests; the two bundled `models/*.7z` remain `provenance-unverified` by construction (lineage only, never accuracy).

## 9. Security Findings and Fixes

All from `DEEP_AUDIT_20261103.md` §2.2; each reproduced → fixed → regression-tested (details in `reports/security/autonomous_session_20261103.md`):

1. **Contract-ID collision** (same content, same second ⇒ same Neo4j MERGE/Postgres key) → id now `c_<stamp>_<sha10>_<uuid4[:8]>`. Test: 50 same-second identical uploads → distinct ids.
2. **Token re-validation** (demoted/deleted user kept access) → JWT claims re-checked against the live `UserStore` on every request; deleted → 401, inflated role → 401. 4 regression tests.
3. **Default secret guard** → `guard_auth_secret` raises at startup in production-ish envs with the shipped default key; CRITICAL log only in dev. 8 regression tests.
4. **`/token` rate limiting** → process-local per-username: 5 consecutive failures → 429 + `Retry-After` for 60 s; lock also blocks the correct password (no credential oracle); success resets. Documented as process-local (not cross-replica).
5. **True oversize 413** → removed dead `file.size` branch; oversize now returns **413** immediately, never truncated-then-parsed.
6. **Job concurrency cap** → per-upload daemon threads replaced by a bounded `ThreadPoolExecutor` (`JOB_WORKER_COUNT=4` default, added to `Settings` + `.env.example`); eviction race quieted in `84340a2`.
7. **Error hygiene** → 500 body generic in production (locked by test).
8. **RLS re-check + post-eviction fallback** → user B still 404 on user A's job after in-memory eviction (Postgres fallback path).

**Left unfixed (documented, needs decision):** `AUTH_USERS` parse-failure silently falls back to the seeded admin — a behavior change beyond the assigned task list, flagged for approval in the security report. Other intentionally-untouched §2.2 items: `playbook_id` unused form field, `uploads/` never cleaned, `/healthz` triggers Neo4j connect, psycopg2-specific `connect_args`, `fetch_graph` O(all edges).

**No authentication or authorization was weakened anywhere to make a test pass.**

## 10. Evaluation Improvements

New tooling + honest, labeled results (full reports in `reports/evaluations/`):

- **Rules-only vs hybrid** (`scripts/eval_rules_vs_hybrid.py`, 2000-row stratified sample, seed 20261103) — **IN-DISTRIBUTION TRAINING-CORPUS only** (banner in report): rule-only Acc@1 **0.337**, hybrid Acc@1 **0.916**. This is *not* a generalization estimate.
- **Risk-booster delta** — 63 `ML_RISK_001` findings added, **0 redundant** with rule findings; all unverified review prompts, not verified findings.
- **Family-leakage analysis** (`nlp/evaluation/family_split.py`, title + 8-gram shingle proxy, threshold 0.5) — **7/102** CUAD test docs share a family with train docs; **95/102** family-disjoint.
- **Family-disjoint held-out** (`scripts/eval_heldout.py`, 5039 annotated examples from the 95 disjoint docs) — the closest legitimate generalization number available: rule-only Acc@1 **0.184**, hybrid Acc@1 **0.401** (top-3: 0.253 / 0.532). Labeled: CUAD is a US dataset; in-dataset generalization within CUAD only.
- **Dataset provenance** — **no license file exists anywhere under `data/datasets/`**; the prior phase_2c "CC BY 4.0" claim is recorded as an unverified prior claim. Neither dataset supports Indian-law compliance claims.

**No gold labels were modified to make results pass; no synthetic results presented as real-world accuracy.**

## 11. Indian-Contract Coverage Limitations

- 5 new synthetic Indian samples (NDA, employment, VSA, DPA, consulting) + 2 new high-precision rules: `RISK_NONCOMPETE_001` (s.27 ICA, post-employment restraint only — in-employment non-solicits, confidentiality, IP assignment do **not** trigger it) and `RISK_DISPUTE_001` (document-wide absence of any dispute-resolution mechanism). Both verified live in §3.
- **Limitations (stated in `reports/evaluations/indian_coverage_20261103.md`):**
  - All samples are **synthetic** (fictional parties/CINs); they are regression locks for pipeline behavior, not evidence of real-document performance.
  - **12 of 26 internal classifier categories have zero training rows** — rule-only; ML-backed coverage is 14 categories (US-derived).
  - Case-law references are statute-only or plain-law notes with `verified_on=None` + honest `verify_note`; **no citation is verified** in-repo.
  - **No Indian-law correctness claim is possible** from US-origin training data.
  - Party detection over-counts on 2 samples (3 parties where 2 are expected) — NER entity boundary limitation, not fixed this session.

## 12. Remaining Defects

1. `AUTH_USERS` parse-failure → silent admin fallback (needs a decision; security report §Remaining).
2. Full-suite exit-code anomaly (non-zero exit despite all-pass, loguru sink-write race at teardown) — **did not reproduce** on the main agent's clean runs; monitor, no code change.
3. Streamlit bearer-token support absent (UI out of scope this session; API-level auth is complete).
4. pdfplumber cosmetic mid-word line breaks near right margins — slice invariant holds; text not byte-identical to source (documented).
5. Character offsets are into cleaned text, not the raw file — documented design decision, not a defect.
6. OCR (tesseract) absent in this container — scanned-PDF path verified only as graceful failure with an explicit OCR hint; no OCR results are invented.
7. Party-detection over-counting (see §11).
8. Untouched P2 backend items listed in §9.

## 13. Local Commit Hashes

Session start → integration (29 workstream commits): see `git log --oneline f0bad0a..fc400a6` (full list in §4). Final HEAD after workstreams: **`fc400a6`**.

This report's commit (docs only: adds this report, renames the stale Phase 2B report to `reports/engineering/autonomous_execution_phase2b_20261102.md`, updates `AI_WORKING_NOTES.md`): see `git log -1` after this commit — one commit on top of `fc400a6`, making the branch **48 ahead** of `origin/main`.

## 14. No-Push Confirmation

**Nothing was pushed to any remote.** All commits are local to `main`. `git rev-list --count origin/main..HEAD` grew 18 → 48 entirely from local commits. No history was rewritten; no destructive git operations were performed; `sync.log` and all unrelated user files were preserved.

## 15. Next Recommended Engineering Task

**Highest value: close the party-detection over-counting defect and the NER entity-boundary issues it exposes** (2 of 6 bundled Indian samples detect a phantom third "party"), because party attribution propagates into every obligation's `subject`/`counterparty` and into `affected_parties` on risk findings — the two fields the reviewer UI will surface first. Concrete steps: (1) add regression fixtures where a party name appears as a substring of an entity span (the observed failure mode), (2) tighten `_detect_parties` windowing in `app/services/analyzer.py` (the file already received the dead-code fix in `30ba884`), (3) re-run `tests/test_indian_contracts.py` and the obligation field-completeness suite. After that: the single open security decision (item 1 in §12).

---

*Evidence standard: items marked ✅ in §3 were re-executed by the main agent in this session; items marked (subagent) rest on committed regression tests and workstream reports. Independently verified results are distinguished from subagent claims throughout.*
