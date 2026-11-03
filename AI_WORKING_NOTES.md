# BharatContract AI — AI Working Notes

> Self-maintained notes file. Records what the AI assistant has understood about this
> repo, what it has done, and what it verified — so no work is lost across sessions.
> Newest sections appended at the bottom.

---

## 1. What this project is

**BharatContract AI** — a legal contract intelligence platform tuned for the Indian
legal context (also usable for global cross-border deals). Upload a contract
(PDF/DOCX/TXT), and it:

1. Parses the document (pdfplumber → PyMuPDF → OCR fallback for scanned PDFs).
2. Segments it into clauses (regex heading detection + long-clause splitting).
3. Classifies each clause (rule/keyword bank + TF-IDF/LogReg hybrid; optional
   DeBERTa-v3 when the `[ml]` extra is installed).
4. Extracts entities via regex-first NER: parties, dates, CIN/PAN/GSTIN/TAN,
   INR amounts, notice periods, arbitration seat vs venue, governing law.
5. Extracts obligations (subject / action / object / deadline) via
   deontic modal-verb patterns.
6. Scores risk with an explainable, rule-first engine that includes
   Indian-statutory rules (Stamp Duty, TDS, §124 indemnity gap, BALCO/BGS SGS
   arbitration seat/venue mismatch, foreign governing law in a domestic
   contract) plus a global playbook (uncapped liability, auto-renewal, broad
   indemnity, one-sided termination, missing mandatory clauses). Every finding
   carries statutory / case-law pointers (`nlp/risk_scoring/case_law.py`).
   A weakly-supervised ML risk classifier (`risk_model.py`) acts as a recall
   booster only (`ML_RISK_001`) for clauses the rules miss, and no-ops when the
   bundled artefact is absent.
7. Persists the full picture to Neo4j (graph: Contract → Clause → Obligation →
   Risk → Party) and PostgreSQL (contract/job metadata, including `owner`).
8. Optionally enforces JWT bearer auth + RBAC (`viewer < analyst < admin`) and
   row-level security (owner-scoped reads; 404, not 403, for others).
9. Serves results via FastAPI (`app/`) and a Streamlit dashboard (`streamlit_app/`).

**Hard architectural rule:** graceful degradation. Neo4j / Postgres /
torch+transformers / OCR being unavailable must all no-op or fall back, never
raise. The full demo runs with zero infra beyond Python.

## 2. Stack & tooling

- Python 3.10–3.12, managed with **uv** (`pyproject.toml` + `uv.lock` + `uv.toml`
  with `link-mode = "copy"`). This is **not** an npm/Node project.
- FastAPI + Uvicorn backend; Streamlit + streamlit-agraph frontend.
- Neo4j (graph), PostgreSQL (metadata via SQLAlchemy + Alembic), Redis (reserved
  for future Celery workers).
- Heavy ML (torch/transformers/DeBERTa) lives in the optional `[ml]` extra.
- Lint with `ruff`; tests with `pytest`.
- Config only via `app/core/config.get_settings()` (pydantic-settings); never
  read `os.environ` directly elsewhere.
- Timestamps via `app/core/time.utcnow()` (naive UTC); never `datetime.utcnow()`
  (deprecated in 3.12).
- Every module keeps `from __future__ import annotations` and a one-line
  docstring.

## 3. Repository map (what lives where)

```
app/                        FastAPI backend
  main.py                   app factory, lifespan, CORS, exception handlers,
                            / and /healthz (healthz exposes a `provenance` block
                            and `auth_enabled` flag)
  api/                      routes: routes_contracts.py (upload + summary/clauses/
                            obligations/risks), routes_jobs.py, routes_graph.py,
                            routes_auth.py (token + me), deps.py (principal +
                            require_role)
  core/                     config.py, logging.py (loguru), exceptions.py,
                            security.py (bcrypt w/ PBKDF2 fallback, HS256 JWT,
                            UserStore), time.py (utcnow helper)
  db/                       neo4j.py (lazy driver, 10s reconnect throttle),
                            postgres.py (SQLAlchemy + _AVAILABLE_CACHE fast-fail,
                            owner columns), queries.py (Cypher MERGE writers,
                            fetch_graph, write_analysis)
  models/schemas.py         Pydantic models (Clause, Obligation, RiskFlag,
                            CaseLawReference, ContractSummary, AnalysisResult,
                            JobInfo, Graph*)
  services/                 parser.py (PDF/DOCX/TXT + OCR), segmenter.py,
                            analyzer.py (pipeline orchestrator), jobs.py
                            (in-memory cap 200 + DB persistence, daemon thread)
  utils/                    text.py (cleaning, heading regex), fs.py (safe
                            filename, save_upload, unique_id)

nlp/                        NLP modules
  taxonomy.py               SINGLE source of truth: INTERNAL_LABELS +
                            CUAD/MAUD → internal label maps
  clause_classification/    classifier.py (hybrid rule + TF-IDF, 26 categories,
                            CUAD keyword bank, letter-boundary matching),
                            tfidf_model.py (extracts models/tfidf_classifier.7z
                            via py7zr, canonicalises labels), classifier_ml.py
                            (optional DeBERTa wrapper)
  ner/                      ner.py (regex-first: CIN/LLPIN/PAN/GSTIN/TAN, INR
                            amounts, dates, notice periods, seat/venue/law),
                            ner_ml.py (optional DeBERTa enrichment)
  obligation_extraction/    extractor.py (modal-verb patterns → obligations with
                            risk level)
  risk_scoring/             rules.py (Indian + global rules), scorer.py (weighted
                            contract score), case_law.py (rule → statutory /
                            landmark citations), risk_model.py (ML recall booster)
  datasets/                 unified.py, cuad.py, maud.py (corpus loaders),
                            splits.py (hash-pinned source allowlist),
                            manifest.py (artifact manifests)
  evaluation/               harness.py, metrics.py, cases.py,
                            metrics_integration.py, regression_detector.py,
                            gold_annotations/cases_gold.json (17 synthetic cases)
  provenance.py             runtime provenance surface

streamlit_app/              Dashboard
  Home.py                   upload page, API-first with in-process fallback,
                            bundled-sample demo button
  api_client.py             httpx helpers + analyse_locally
  components/risk_card.py   badge / header / risk_card / clause_card
  pages/                    1_Summary, 2_Clause_Explorer, 3_Obligations,
                            4_Graph (agraph + in-memory fallback),
                            5_Risk_Review

data/                       raw/ (sample_msa.txt), processed/ (generated, not
                            shipped: clause_classifier.csv, *_examples.jsonl,
                            cuad_keyword_bank.json),
                            datasets/ (CUAD + MAUD)
models/                     bundled tfidf_classifier.7z + risk_classifier.7z
                            (extracted on first use), PROVENANCE_STATUS.json
docker/                     Dockerfile + docker-compose.yml
scripts/                    run_demo.py, build_training_data.py,
                            train_tfidf_classifier.py, train_risk_classifier.py,
                            eval_classifier.py, run_evaluation.py,
                            check_evaluation_regression.py,
                            verify_provenance.py, inspect_*/debug_* helpers
tests/                      ~262 tests: parser, segmenter, long clauses,
                            classifier accuracy floors, e2e, api smoke, auth,
                            RLS, risk model, risk rules, evaluation harness /
                            metrics / integration, regression detector,
                            context resolution, evidence binding, p4 adversarial,
                            no-leakage, regressions
reports/                    evaluations/ + engineering/ + audit/ + recovery/
                            (session reports, baselines, audits)
```

## 4. Pipeline order (do not change casually)

`parse → segment → classify → NER → obligations → risk rules → score`
— orchestrated by `app/services/analyzer.py`. Party detection uses 3 strategies
(NER, suffix-based regex, preamble pattern). `_first_date` picks the contract
date.

## 5. Key invariants & pitfalls (learned from AUDIT_MEMORY.md + plan.md)

- **Taxonomy sync:** classifier labels and dataset loaders must stay in sync with
  `nlp/taxonomy.py`. CUAD/MAUD loaders emit canonical labels only.
- **Job cache:** in-memory `_jobs` capped at 200 is a fast path; Postgres is the
  durable store. `_latest_job_for` (in `routes_contracts.py`) falls back to
  Postgres (`list_job_ids_for_contract`) on a cache miss — do not remove that
  fallback (F7 fix).
- **Provenance ≠ evaluation ≠ predictive validity.** Manifests prove lineage
  only. Both bundled `models/*.7z` are `provenance-unverified` (corpus overlap
  with held-out CUAD). `scripts/verify_provenance.py` is fail-closed (exit 0
  only when everything verifies).
- **Risk labels are rule-derived** — any accuracy figure on `data/processed/`
  is training-overlapping. Synthetic baselines are NOT real-world accuracy.
- **`data/processed/` is generated, not shipped.** Fresh clones run on the
  bundled `models/tfidf_classifier.7z`; run
  `uv run python scripts/build_training_data.py` to regenerate with manifests.
  `BCC_EVAL_MODE=ci` makes a missing corpus a hard test failure instead of a
  skip.
- **Empty/whitespace uploads** are rejected with 400 at the edge (F3 fix).
- **500 handler** only leaks the exception type name in development (F6 fix).
- **`owner` columns** are added best-effort via `ALTER TABLE ... ADD COLUMN IF
  NOT EXISTS` — no migration tool; keep that pattern if adding columns.

## 6. Current state (verified 2026-11-03)

### Git
- Branch: `main`, HEAD `92aaf4b` ("docs: add implementation complete report").
- Working tree clean (before my notes file was added).
- `audit/repo-hardening` branch still exists at the same commit (harmless).
- `origin/main` is behind (local is ahead; push only on explicit go-ahead).

### Verified on this machine (Linux container)
- `.venv` had been created on **Windows** (`win_amd64` .pyd files, no exec bit)
  and failed with "Permission denied" — **rebuilt with `uv venv --python 3.12`
  + `uv sync --extra dev`**. If this ever breaks again, same remedy.
- `uv run pytest` → **262 passed, 3 warnings** (all warnings are third-party:
  starlette/httpx TestClient deprecation, neo4j driver destructor).
- `uv run ruff check .` → 3 pre-existing B008 style warnings in
  `scripts/check_evaluation_regression.py` (typer.Option in argument defaults).
  Deliberately not "fixed" by refactoring; they are the accepted style for typer
  CLIs. (Optional: add a `noqa` or `# ruff: noqa: B008` per-line, or a per-file
  ignore in pyproject, if a clean `ruff check .` is ever required for CI.)
- Demo (`scripts/run_demo.py`) per last report: 12 clauses, 13 obligations,
  risk_score 100 (critical) on the bundled sample MSA.
- Provenance check per last report: 0 failures, 0 skipped.

### Open / known issues (inherited, not mine)
1. `data/processed/` predates provenance in some checkouts — readiness check may
   exit 1 with missing manifests; remediation was gated behind approvals A3/A4
   (see plan.md §8 "Known limitation"). Latest reports say provenance now
   passes 0/0 — re-run `uv run python scripts/verify_provenance.py` if in doubt.
2. Both bundled `models/*.7z` remain `provenance-unverified` by design.
3. Ruff B008 warnings (see above).
4. `tests/test_metrics_integration.py.bak` exists in `tests/` — leftover backup
   file; harmless but could be deleted.
5. Streamlit dashboard does not send bearer tokens (API enforces auth; UI does
   not) — documented deferral in plan.md §9.
6. Deferred post-MVP: surya-ocr/docTR, Indic language support (MuRIL/IndicBERT),
   LLM redline generation, Slack/Jira workflows.

## 7. Common commands

```bash
uv sync --extra dev                 # install (rebuild venv: rm -rf .venv first if it was made on another OS)
uv run pytest -q                    # full test suite (262 tests)
uv run ruff check .                 # lint (3 known B008 warnings)
uv run python scripts/run_demo.py   # CLI demo, no infra needed
uv run uvicorn app.main:app --reload          # API  -> :8000/docs
uv run streamlit run streamlit_app/Home.py    # UI   -> :8501
uv run python scripts/verify_provenance.py    # fail-closed provenance check
uv run python scripts/run_evaluation.py       # synthetic evaluation
uv run python scripts/check_evaluation_regression.py   # regression check
uv run python scripts/build_training_data.py  # regenerate data/processed/
docker compose -f docker/docker-compose.yml up --build   # full stack
```

## 8. Session log

### 2026-11-03 (this session)
- User asked to understand the repo, write notes, and commit so no work is lost.
- Read: README.md, plan.md, AGENTS.md, AUDIT_MEMORY.md,
  IMPLEMENTATION_COMPLETE_20261103.md, HANDOFF_PHASE2B_FINAL.md; surveyed
  app/, nlp/, streamlit_app/, scripts/, tests/, reports/.
- Fixed broken `.venv` (Windows-created venv on a Linux box) by rebuilding with
  uv (Python 3.12).
- Verified: `pytest` → 262 passed; `ruff` → 3 known B008 warnings.
- Created this file.
