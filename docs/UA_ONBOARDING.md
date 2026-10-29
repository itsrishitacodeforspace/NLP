# Onboarding Guide — BharatContract AI

> Auto-generated from the project knowledge graph (`.ua/knowledge-graph.json`). Re-run `/understand` then `/understand-onboard` to refresh.

## Project Overview

- **Name:** BharatContract AI
- **Description:** Legal Contract Intelligence — Indian-context risk-aware clause extraction & obligation tracker
- **Languages:** Python, Markdown, YAML, JSON, TOML, Dockerfile, HTML, CSV, TXT (plus config/unknown)
- **Frameworks:** FastAPI, Streamlit, SQLAlchemy, Alembic, Celery, Neo4j, PostgreSQL, Pydantic, Uvicorn, Pytest
- **Scale:** 278 files; 680 graph nodes (90 files, 349 functions, 47 classes); 969 edges; 10 architectural layers.

BharatContract AI is an end-to-end contract intelligence platform tuned for the Indian legal context while remaining useful for global cross-border agreements. It uploads contracts (PDF/DOCX/TXT with OCR fallback), segments clauses, classifies them (rule-based + TF-IDF, optional DeBERTa-v3), extracts entities (parties, dates, CIN/PAN/GSTIN, INR amounts, notice periods, jurisdictions, arbitration seats), detects obligations (subject/action/object/deadline), and scores risk via an Indian-statutory-aware playbook (stamp duty, arbitration seat/venue mismatch, §124 indemnity gap, foreign governing law, TDS/GST) plus global rules. Results persist to Neo4j (graph) + PostgreSQL (metadata) and are visualised in a Streamlit dashboard.

## Architecture Layers

### 1. API Layer (`layer:api`) — 7 files
FastAPI route handlers, dependency injection, and HTTP entry point for contract analysis endpoints.
Key files:
- `app/main.py` — FastAPI bootstrap: routers, middleware, exception handlers, lifespan (logging + DB init)
- `app/api/routes_contracts.py` — upload, summary, clauses, obligations, risks endpoints
- `app/api/deps.py` — dependency injection: current principal resolution + RBAC
- `app/api/routes_auth.py` — login + `/me`
- `app/api/routes_jobs.py`, `routes_graph.py` — job status, graph fetch

### 2. UI Layer (`layer:ui`) — 9 files
Streamlit multi-page dashboard: summary, clause explorer, obligations, graph, risk review.
Key files: `streamlit_app/Home.py`, `api_client.py`, `components/risk_card.py`, `pages/1_Summary.py` … `5_Risk_Review.py`, `4_Graph.py`

### 3. Service Layer (`layer:service`) — 5 files
Backend services for job orchestration, parsing, segmentation, and analysis pipelines.
Key files: `app/services/analyzer.py` (orchestrator), `parser.py`, `segmenter.py`, `jobs.py`

### 4. NLP Intelligence Layer (`layer:nlp`) — 25 files
Clause classification, NER, obligation extraction, risk scoring, context resolution, dataset provenance.
Key files: `nlp/clause_classification/classifier.py` (+ tfidf_model, classifier_ml), `nlp/ner/ner.py`, `nlp/obligation_extraction/extractor.py`, `nlp/risk_scoring/{rules,scorer,case_law,risk_model}.py`, `nlp/context/resolver.py`, `nlp/taxonomy.py`, `nlp/datasets/*`, `nlp/provenance.py`

### 5. Data Layer (`layer:data`) — 172 files
Database access (Postgres/Neo4j), ORM models, schemas, migrations, bundled datasets/artifacts.
Key files: `app/db/postgres.py`, `queries.py`, `neo4j.py`, `app/models/schemas.py`, `data/datasets/{cuad,maud}/*`

### 6. Configuration Layer (`layer:config`) — 11 files
Settings, security, logging, exceptions, project config.
Key files: `app/core/config.py`, `security.py`, `logging.py`, `exceptions.py`, `time.py`, `pyproject.toml`, `.env.example`

### 7. Utility Layer (`layer:utility`) — 15 files
Filesystem helpers, text utilities, developer scripts.
Key files: `app/utils/fs.py`, `text.py`, `scripts/run_demo.py`, `debug_*.py`

### 8. Infrastructure Layer (`layer:infrastructure`) — 8 files
Docker images, compose services, deployment topology.
Key files: `docker/Dockerfile`, `docker/docker-compose.yml`

### 9. Test Layer (`layer:test`) — 13 files
API, auth, RLS, parser, segmenter, NLP accuracy/regression suites.
Key files: `tests/test_e2e.py`, `test_auth.py`, `test_rls.py`, `test_classifier_accuracy.py`, `test_no_leakage.py`, `test_context_resolution.py`, `test_evidence_binding.py`

### 10. Documentation Layer (`layer:documentation`) — 19 files
Charter, README, plans, reports, session memory.

## Key Concepts

- **Graceful degradation:** Every external dependency (Neo4j, Postgres, torch/transformers, OCR) no-ops or falls back; the demo runs with zero infra beyond Python.
- **Single taxonomy source:** `nlp/taxonomy.py` holds `INTERNAL_LABELS` and CUAD/MAUD → internal maps; classifier and loaders stay in sync.
- **Jobs:** in-memory cache (capped 200) is the fast path; PostgreSQL is the durable store; route lookups fall back to Postgres on cache miss.
- **Risk engine:** rule-first and explainable (`nlp/risk_scoring/rules.py`); Indian-statutory rules run once per contract; others per clause, deduped by `rule_id`.
- **Bundled classifiers:** `models/tfidf_classifier.7z` and `models/risk_classifier.7z` extracted on first use (no 7-Zip binary needed).
- **Auth + RLS:** `AUTH_ENABLED` (default off) gates JWT bearer auth; when on, jobs/contracts carry an `owner` and reads are scoped (404 for others).
- **ML risk classifier:** recall booster only — adds `ML_RISK_001` for clauses with no rule hit; no-ops when artefact missing.
- **Provenance:** generated artifacts carry `<artifact>.manifest.json`; source identity resolved from path + SHA-256 against `nlp/datasets/splits.py` (hash-pinned, not upstream-authenticated). `scripts/verify_provenance.py` is the fail-closed readiness check.
- **Pipeline order:** parse → segment → classify → NER → obligations → risk rules → score, orchestrated by `app/services/analyzer.py`.

## Guided Tour

1. **Project Overview** — `document:README.md`
2. **Application Entry Point** — `app/main.py`
3. **Core Models and Config** — `app/models/schemas.py`, `app/core/config.py`
4. **API Layer and Auth** — `app/api/routes_contracts.py`, `deps.py`, `routes_auth.py`
5. **Service Pipeline** — `app/services/analyzer.py`, `parser.py`, `segmenter.py`
6. **Clause Classification** — `nlp/clause_classification/classifier.py`, `tfidf_model.py`, `classifier_ml.py`
7. **NER and Obligation Extraction** — `nlp/ner/ner.py`, `nlp/obligation_extraction/extractor.py`
8. **Risk Scoring** — `nlp/risk_scoring/scorer.py`, `rules.py`, `risk_model.py`
9. **Context Resolution and Taxonomy** — `nlp/context/resolver.py`, `nlp/taxonomy.py`
10. **Data and Graph Persistence** — `app/db/postgres.py`, `queries.py`, `neo4j.py`
11. **Streamlit Dashboard** — `streamlit_app/Home.py`, `api_client.py`, `components/risk_card.py`
12. **Containerization and Deployment** — `service:docker/Dockerfile`, `service:docker/docker-compose.yml`
13. **Dataset Provenance and Training** — `nlp/datasets/cuad.py`, `nlp/provenance.py`, `scripts/build_training_data.py`

## File Map (key files by layer)

| Layer | Key files |
| --- | --- |
| API | `app/main.py`, `app/api/routes_contracts.py`, `deps.py`, `routes_auth.py`, `routes_jobs.py`, `routes_graph.py` |
| UI | `streamlit_app/Home.py`, `api_client.py`, `components/risk_card.py`, `pages/*.py` |
| Service | `app/services/analyzer.py`, `parser.py`, `segmenter.py`, `jobs.py` |
| NLP | `nlp/clause_classification/*`, `nlp/ner/ner.py`, `nlp/obligation_extraction/extractor.py`, `nlp/risk_scoring/*`, `nlp/context/resolver.py`, `nlp/taxonomy.py`, `nlp/provenance.py` |
| Data | `app/db/{postgres,queries,neo4j}.py`, `app/models/schemas.py` |
| Config | `app/core/{config,security,logging,exceptions,time}.py`, `pyproject.toml`, `.env.example` |
| Utility | `app/utils/{fs,text}.py`, `scripts/*` |
| Infra | `docker/Dockerfile`, `docker/docker-compose.yml` |
| Test | `tests/test_e2e.py`, `test_auth.py`, `test_rls.py`, `test_classifier_accuracy.py`, `test_no_leakage.py`, `test_context_resolution.py`, `test_evidence_binding.py` |

## Complexity Hotspots

Approach these carefully (marked `complex`):

- `nlp/clause_classification/classifier.py` — rule-based keyword matcher + CUAD keyword bank + TF-IDF ML fallback
- `nlp/risk_scoring/risk_model.py` — weakly-supervised ML risk classifier (TF-IDF + LogisticRegression)
- `streamlit_app/pages/4_Graph.py` — interactive contract knowledge graph explorer
- `tests/test_no_leakage.py` — provenance/no-leakage tests for training corpus and manifests
- `data/datasets/maud/data/raw/{abridged,counterfactual,main}.csv` — large MAUD annotation matrices

## Quick Start (from README)

```bash
uv sync --extra dev
docker compose -f docker/docker-compose.yml up -d neo4j postgres redis
uv run uvicorn app.main:app --reload          # API -> :8000/docs
uv run streamlit run streamlit_app/Home.py    # UI  -> :8501
uv run python scripts/run_demo.py            # CLI demo, no infra
uv run pytest -q                             # tests
```

---

*Generated by `/understand-onboard` from `.ua/knowledge-graph.json`. Commit this file to the repo for the team.*