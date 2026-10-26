# Memory

## Project Overview
See @README.md for the full project overview and @plan.md for the architectural
source of truth and execution checklist.

**Stack:** Python 3.10–3.12, managed with **uv** (`pyproject.toml` + `uv.lock`).
This is **not** an npm/Node project — there is no `package.json`; ignore any
legacy reference to one.

Components: FastAPI backend (`app/`), Streamlit dashboard (`streamlit_app/`),
rule-first NLP modules (`nlp/`), helpers (`scripts/`), tests (`tests/`),
Docker stack (`docker/`). Data persistence: Neo4j (graph) + PostgreSQL (metadata)
+ Redis (reserved for Celery). Heavy ML (DeBERTa via torch/transformers) is an
optional `[ml]` extra — the stack runs fully without it.

## Code Style Guidelines
- Use descriptive variable names.
- Follow existing patterns in the codebase.
- Extract complex conditions into meaningful boolean variables.
- Every module keeps its `from __future__ import annotations` header and a
  one-line docstring; keep that convention.
- Config only via `app.core.config.get_settings()` — do not read `os.environ`
  directly outside that module.
- Timestamps: use `app.core.time.utcnow()` (naive UTC). Do **not** use
  `datetime.utcnow()` (deprecated in 3.12).

## Architecture Notes
- **Pipeline order:** parse → segment → classify → NER → obligations → risk rules
  → score. Orchestrated by `app/services/analyzer.py`.
- **Graceful degradation is a hard requirement:** every external dependency
  (Neo4j, Postgres, torch/transformers, OCR) must no-op or fall back rather than
  raise. The demo must run with zero infra beyond Python.
- **Single taxonomy source:** `nlp/taxonomy.py` holds `INTERNAL_LABELS` and the
  CUAD/MAUD → internal maps. Classifier labels and dataset loaders must stay in
  sync with it.
- **Jobs:** in-memory cache (`app/services/jobs.py`, capped at 200) is a fast path;
  PostgreSQL is the durable store. Route lookups fall back to Postgres on a cache
  miss (see `_latest_job_for` in `app/api/routes_contracts.py`).
- **Risk engine:** rule-first and explainable (`nlp/risk_scoring/rules.py`);
  Indian-statutory rules run once per contract (stamp duty, TDS, §124 indemnity),
  others per clause and are de-duplicated by `rule_id`.
- **Bundled classifiers:** `models/tfidf_classifier.7z` and `models/risk_classifier.7z` are
  extracted on first use by `tfidf_model.py` / `risk_model.py` (no 7-Zip binary required).
- **Auth + row-level security:** `AUTH_ENABLED` (default off) gates bearer-token auth
  (`app/core/security.py`, `app/api/deps.py`, `routes_auth.py`). When on, jobs/contracts carry an
  `owner` and reads are scoped to the caller (404, not 403, for others). Off ⇒ everything is open.
- **ML risk classifier:** `nlp/risk_scoring/risk_model.py` is a *recall booster* only — it adds
  `ML_RISK_001` findings for clauses with no rule hit, and no-ops when the artefact is missing.
- **Provenance:** generated artifacts carry `<artifact>.manifest.json`; source identity is resolved from
  file path + SHA-256 against `nlp/datasets/splits.py` (hash-pinned, **not** upstream-authenticated).
  `scripts/verify_provenance.py` is the fail-closed readiness check (exit 0 only when everything verifies).
  `/healthz` exposes a `provenance` block; analysis warnings carry `PROVENANCE_*` tokens. The bundled
  `models/*.7z` are `provenance-unverified` (trained on a corpus overlapping held-out CUAD). Keep
  **artifact provenance / evaluation / predictive validity** strictly separate — a manifest proves
  lineage only, never accuracy.

## Common Workflows
```bash
uv sync --extra dev                 # install (uv-first)
uv run pytest -q                    # tests
uv run ruff check .                 # lint
uv run python scripts/run_demo.py   # CLI demo, no infra needed
uv run uvicorn app.main:app --reload            # API  -> :8000/docs
uv run streamlit run streamlit_app/Home.py      # UI   -> :8501
docker compose -f docker/docker-compose.yml up --build   # full stack
```
Rebuild the training corpus / keyword bank: `uv run python scripts/build_training_data.py`.
