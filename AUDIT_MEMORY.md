# BharatContract AI — Continuous Audit Memory

> Append-only thought journal. Each entry is timestamped (UTC) and records what I
> looked at, what I concluded, and what I plan next. Newest entries at the bottom.
> Branch: `audit/repo-hardening`. Session date: 2026-10-25.

---

## 2026-10-25T~14:30Z — Session start, orientation

**Goal (user):** "complete this project" + understand all files + keep this timestamped
memory. User chose all four scopes: (1) live-runtime verification + bug hunt,
(2) build deferred post-MVP features, (3) merge hardening branch to main,
(4) deep bug-hunt audit.

**Repo state at start**
- Branch `audit/repo-hardening`, **2 commits ahead of `main`**, unmerged.
- Working tree clean except untracked `.commandcode/` and `AGENTS.md`.
- `uv 0.12.6` works; `.venv` resolves to `.venv\Scripts\python.exe`.
- No `.env` file (defaults are dev-friendly, so the stack still runs).
- `uv run pytest -q` → **24 passed**. `uv run ruff check .` → **clean**.
- `uv run python scripts/run_demo.py` → full report: parties detected, seat=Singapore,
  risk_score=100 (critical).

**Conclusion:** nothing is visibly unfinished; "complete" is about hardening + verifying
runtime + extending. Ledger created: task #1 live-runtime/bug-hunt, #2 deferred features,
#3 merge to main.

---

## 2026-10-25T~14:35Z — Full file map (all 69 source files read)

### Root
- `README.md` — project intro (FastAPI + Streamlit + Neo4j + Postgres + DeBERTa + spaCy).
- `plan.md` — "single source of truth". Phases 1–6 + hardening pass all marked `[x]`.
  Only two open items: **live FastAPI boot not verified**, **live Streamlit boot not verified**.
  Section 8 lists deferred post-MVP work.
- `AGENTS.md` — memory stub (references README/package.json — note: **no package.json exists**;
  this project is Python/uv, so the AGENTS.md reference is stale/wrong).
- `pyproject.toml` — deps + `[ml]`, `dev` extras; ruff config; hatchling build.
- `requirements.txt` — separate pinned list (torch/transformers/spacy/etc.).
- `uv.toml` (`link-mode="copy"`), `uv.lock`, `.env.example`, `.gitignore`, `.dockerignore`.

### app/ (FastAPI backend)
- `main.py` — app factory, lifespan touches Neo4j, CORS middleware, domain + generic
  exception handlers, `/` and `/healthz` routes.
- `core/config.py` — pydantic-settings `Settings`, `get_settings()` lru_cached, `ensure_dirs()`.
- `core/logging.py` — loguru, stderr + rotating file, `setup_logging()` idempotent.
- `core/exceptions.py` — `BharatContractError` + parse/format/model/graph subclasses w/ status codes.
- `api/routes_contracts.py` — `POST /upload` (ext check, size pre-check + read cap,
  contract_id = sha256+timestamp, background job), GET summary/clauses/obligations/risks.
- `api/routes_jobs.py` — `GET /jobs/{id}`, `GET /jobs`.
- `api/routes_graph.py` — `GET /graph/{id}` w/ in-memory fallback from job result.
- `models/schemas.py` — all Pydantic enums/models (Clause, Obligation, RiskFlag,
  ContractSummary, AnalysisResult, JobInfo, Graph*).
- `db/neo4j.py` — lazy driver, throttled reconnect (10s), `ensure_indexes`, `run_read/write`.
- `db/postgres.py` — SQLAlchemy models (ContractRecord, JobRecord), `_AVAILABLE_CACHE`
  fast-fail, upsert helpers.
- `db/queries.py` — Cypher MERGE writers + `fetch_graph` + `write_analysis`.
- `services/parser.py` — PDF (pdfplumber→PyMuPDF→OCR), DOCX, TXT/MD; `parse_bytes` saves to
  disk via `save_upload`; char cap 2M; header/footer stripper.
- `services/segmenter.py` — heading detection + long-clause split (paragraph→sentence→fixed).
- `services/analyzer.py` — orchestrator: segment→classify→NER→obligations→rules→score;
  `_detect_parties` (3 strategies), `_first_date`.
- `services/jobs.py` — in-memory `_jobs` dict (cap 200) + DB persistence, daemon-thread runner.
- `utils/text.py` — cleaning/normalise, heading regex, paragraph split.
- `utils/fs.py` — `safe_filename`, `save_upload`, `derive_title_from_filename`, `remove_path_safely`, `unique_id`.

### nlp/
- `taxonomy.py` — canonical INTERNAL_LABELS + CUAD→internal + MAUD→internal maps.
- `clause_classification/classifier.py` — hybrid rule (keyword bank, letter-boundary regex)
  + TF-IDF; `CLAUSE_RULES` (26 categories), `HEADING_HINTS`.
- `clause_classification/tfidf_model.py` — extracts `models/tfidf_classifier.7z` via py7zr,
  canonicalises labels, `TrainedClassifier`.
- `clause_classification/classifier_ml.py` — optional DeBERTa wrapper (lazy, no-op fallback).
- `ner/ner.py` — regex CIN/LLPIN/PAN/GSTIN/TAN/amounts/dates/notice; seat & law detection.
- `ner/ner_ml.py` — optional DeBERTa token-classification enrichment.
- `obligation_extraction/extractor.py` — deontic modal patterns → Obligation rows; risk level.
- `risk_scoring/rules.py` — 10 rules (Indian + global) + missing-clause + contract-level.
- `risk_scoring/scorer.py` — weighted contract score + severity→score.
- `datasets/{unified,cuad,maud}.py` — training-corpus loaders.

### streamlit_app/
- `Home.py` — upload page, API-first w/ in-process fallback, bundled-sample demo button.
- `api_client.py` — httpx helpers + `analyse_locally`.
- `components/risk_card.py` — badge/header/risk_card/clause_card.
- `pages/1_Summary.py`, `2_Clause_Explorer.py`, `3_Obligations.py`, `4_Graph.py`
  (streamlit-agraph), `5_Risk_Review.py`.

### scripts/ (10)
`run_demo.py`, `build_training_data.py`, `train_tfidf_classifier.py`, `eval_classifier.py`,
`inspect_classifier_corpus.py`, `inspect_cuad.py`, and 4 `debug_*.py`
(two of which hard-code a stale upload path `uploads/c_20260818_...pdf`).

### tests/ (7, 24 cases)
parser, segmenter, long_clauses, classifier_accuracy, e2e, api_smoke, regressions.

### Data / models present
- `data/datasets/cuad/` (CUADv1.json etc.), `data/datasets/maud/data/`.
- `data/processed/` — clause_classifier.csv, *_examples.jsonl, cuad_keyword_bank.json.
- `models/tfidf_classifier.7z` + extracted `.joblib`; `models/hf/` deberta cache (partial).
- `uploads/` littered with leftover `c_*_sample_msa.txt` from repeated test runs (gitignored).

---

## 2026-10-25T~14:40Z — Observations / candidate defects (to verify)

1. **`datetime.utcnow()` deprecation** — used in `schemas.py`, `postgres.py`, `routes_contracts.py`,
   `utils/fs.py`, `services/jobs.py`. Emits DeprecationWarning on py3.12. Low severity, easy fix.
2. **AGENTS.md references `package.json`** — nonexistent (Python project). Stale memory.
3. **`_latest_job_for` is in-memory only** — if the 200-job cap evicts a succeeded job,
   `GET /summary|clauses|...` 404s even though the result may exist in Postgres. Possible bug.
4. **`GET /upload` ignores `?async_mode=true`** in the smoke test — the route always runs async;
   harmless (extra query param silently ignored).
5. **`file.size` check** — relies on Starlette UploadFile.size; the read-cap afterwards covers it.
6. **Generic 500 handler leaks `type(exc).__name__`** — minor info disclosure.
7. **`debug_normalised.py` / `debug_segmenter.py`** point at a non-existent upload PDF.
8. **`postgres.list_jobs`** returns only `{"job_id": ...}` — thin; fine given usage.
9. **`run_write` retry** — `execute_write` lambda returns `.consume()`; acceptable.
10. **`_connect` catches `(ServiceUnavailable, Exception)`** — redundant tuple; cosmetic.
11. **Live-boot: earlier `uvicorn` bg start produced an EMPTY log and refused connections** —
    needs re-investigation (possible stdout buffering under the task runner, or slow uv sync).
    Still unverified: real HTTP server boot for both API and Streamlit.

**Plan next:** re-run the live API boot carefully (uvicorn, explicit log), exercise the full
endpoint path incl. error cases (bad ext, oversized, empty, unknown contract), then Streamlit boot.

---

## 2026-10-25T~15:05Z — Live API verification: PASSED ✅

Booted `uv run python -m uvicorn app.main:app --port 8020` for real. Findings:
- API up ~3s after start. Earlier "empty log + refused" was **cold-start latency + buffered
  stdout under the task runner**, NOT a bug. Server is fine.
- `GET /`, `/healthz`, `/docs`, `/openapi.json`, `/api/v1/jobs` → 200.
- `POST /upload` (sample MSA) → 200; job polled to `succeeded` (12 clauses, 12 obligations,
  10 risks); `GET summary/clauses/obligations/risks/graph` → 200 (graph 35 nodes / 31 edges).
- Error cases: bad ext → **400**, unknown contract → **404**, unknown job → **404**,
  non-multipart → **422**, 26 MB upload → **413**, empty file → 200 then job **failed** with a
  clear message, whitespace-only file → same. So oversized/empty are handled; empty just fails
  asynchronously rather than at upload time (candidate UX improvement, not a bug).

**Plan item 1 of 2 closed: live FastAPI server boot verified.**

## 2026-10-25T~15:10Z — Machine restarted mid-session

User restarted the computer; all background servers/tasks killed. State intact: repo clean
(+ untracked `.commandcode/`, `AGENTS.md`, `AUDIT_MEMORY.md`), still on `audit/repo-hardening`
@ `b915cfa`. Resume at: **Streamlit live boot** (was inconclusive — never came up before the
restart; log empty/buffered, port not confirmed listening).

---

## 2026-10-25T~17:20Z — Live Streamlit verification: PASSED ✅

- `streamlit run streamlit_app/Home.py --server.headless true --port 8520` boots and serves:
  `/_stcore/health` → 200, `/` → 200 (HTML shell 10951 bytes), `/_stcore/host-config` → 200.
- Stronger check: ran Streamlit `AppTest` on all 6 scripts (Home + 5 pages) with a **real**
  analysis injected into session_state. **All 6 → OK, zero exceptions.**
- API re-booted on default :8000 as well.

**Plan item 2 of 2 closed: live Streamlit boot verified.** Both plan.md "not verified" items done.

**Deprecation warning surfaced (real, time-relevant):**
- `st.dataframe(..., use_container_width=True)` in `pages/3_Obligations.py:103`. Streamlit says
  "will be removed after 2025-12-31" — today is 2026-10-25, i.e. already past. → migrate to
  `width="stretch"`.

## 2026-10-25T~17:25Z — Fix list (from verification + audit)

- F1 `datetime.utcnow()` (7 sites: schemas ×2, postgres ×4, jobs ×2, routes_contracts ×1,
  fs ×1) → timezone-safe helper.
- F2 `use_container_width` → `width="stretch"` (3_Obligations.py).
- F3 Empty / whitespace-only upload → reject at upload time with 400 (better UX than a
  job that fails 3s later).
- F4 `AGENTS.md` stale ("see @package.json" — no package.json in a Python/uv project).
- F5 `scripts/debug_normalised.py` / `debug_segmenter.py` hard-code a non-existent upload PDF.
- F6 Generic 500 handler leaks `type(exc).__name__` to clients (info disclosure).
- F7 `_latest_job_for` only searches in-memory jobs → after the 200-job eviction cap (or a
  restart with Postgres healthy) a contract's summary can 404 despite a stored result.

## 2026-10-25T~17:50Z — Fixes applied & re-verified ✅

- **F1** new `app/core/time.py::utcnow()` (naive UTC via `datetime.now(timezone.utc)`);
  replaced all 7 `datetime.utcnow()` call sites (schemas ×2, postgres ×3 + 1 onupdate,
  jobs ×2, routes_contracts, fs). Removed now-unused `datetime` imports.
- **F2** `3_Obligations.py`: `use_container_width=True` → `width="stretch"`
  (installed Streamlit is **1.61.1**, supports it).
- **F3** upload rejects empty/whitespace-only bodies with **400** (was 200 + late job failure).
- **F4** `AGENTS.md` rewritten: dropped the bogus `@package.json` reference; documented
  uv-first commands, pipeline order, graceful-degradation rule, taxonomy source, job model.
- **F5** `debug_normalised.py` / `debug_segmenter.py` now point at `data/raw/sample_msa.txt`
  instead of a missing PDF.
- **F6** generic 500 handler only includes `type` in the body when `app_env` is development.
- **F7** added `postgres.list_job_ids_for_contract()`; `_latest_job_for` now falls back to
  Postgres after an in-memory miss.

**Re-verification after fixes**
- `uv run ruff check .` → clean.
- `uv run pytest` → **24 passed, 3 warnings**; warnings are now only third-party
  (neo4j driver destructor) — **no more `utcnow` warnings from our code**.
- Live API re-probe: all endpoints OK; empty file → **400**; oversize → 413; bad ext → 400.
- Streamlit AppTest on all 6 pages → **all OK**.

Next: task #2 — build a pragmatic subset of deferred post-MVP features.

---

## 2026-10-25T~18:05Z — Deferred features built (task #2)

Of the six section-8 backlog items I built the two that need **no external
service or model** and directly serve the Indian-legal positioning; the rest
need external infra/models and I left them deferred (reported to the user).

**1. Case-law / statutory augmentation** (`nlp/risk_scoring/case_law.py`)
- Curated `CASE_LAW: rule_id -> [{citation, summary, jurisdiction}]` mapping
  (Stamp Act ss. 33/35, *Hindustan Steel v. Dilip Construction*, *BALCO*,
  *BGS SGS Soma* + Arb. Act s.2(2)/20, Contract Act ss.124–125,
  *Gajanan Moreshwar Parelkar*, Income Tax Act s.194C/194J/201/40(a)(ia),
  Contract Act s.28, *Brojo Nath Ganguly*, *ONGC v. Saw Pipes*, DPDP Act 2023).
- New `CaseLawReference` schema + `RiskFlag.case_law`; attached in `apply_rules`.
- Surfaced in the Streamlit risk card (expander) and the risks JSON export.
- Explicit "not legal advice" warning in the module docstring.
- Verified end-to-end: sample MSA risks now carry pointers per rule.

**2. Authentication & RBAC** (optional, `AUTH_ENABLED`, default **false**)
- `app/core/security.py`: bcrypt hashing **direct** (passlib 1.7.4 is broken
  against installed bcrypt 5.0 — `__about__` removed) with a stdlib
  PBKDF2-HMAC-SHA256 fallback; HS256 JWT via python-jose; process-local
  `UserStore` seeded from `AUTH_USERS` else `AUTH_ADMIN_PASSWORD`.
- `app/api/deps.py`: `get_current_principal` + `require_role(...)` (ranked
  roles viewer<analyst<admin; no-op when auth disabled so nothing breaks).
- `app/api/routes_auth.py`: `POST /api/v1/auth/token`, `GET /api/v1/auth/me`.
- `POST /api/v1/contracts/upload` now requires analyst+ when auth is enabled.
- Config + `.env.example` + README section + healthz `auth_enabled` flag.
- `tests/test_auth.py` (4 cases). **Live-verified** on :8021 with AUTH_ENABLED:
  no token → 401, viewer upload → 403, viewer /me → 200, analyst upload → 200,
  garbage token → 401.

**Deliberately NOT done (need external services/models):** LLM redline generation
(needs an LLM), Hindi/Indic support (MuRIL/IndicBERT), Slack/Jira workflows; and
the ML risk classifier (no labelled risk data — would be self-referential).

**Docs updated:** README (case-law + auth section + env table + tests), plan.md
(new "Verification Pass & Extensions" section, status → 2026-10-25), .env.example.

**Final checks:** `ruff check .` clean; `pytest` → **29 passed** (24 + case-law + 4 auth).

---
