# BharatContract AI — Living Plan & Execution Checklist

> Status: 🚧 **Phase 1 — Foundation** (autonomous execution in progress)
> Last update: 2026-08-18

This document is the **single source of truth**. Items prefixed `[ ]` are pending,
`[x]` are completed, `[~]` are partially done.

---

## 0. Project Identity
- **Name:** BharatContract AI (Legal Contract Intelligence)
- **Focus:** Indian Corporate, Commercial, M&A contracts + global cross-border.
- **Stack:** FastAPI · Streamlit · Neo4j · PostgreSQL · Redis · DeBERTa · spaCy.

---

## 1. Phase 1 — Foundation
- [x] Create folder layout (`app/`, `streamlit_app/`, `nlp/`, `data/`, `docker/`, `tests/`...).
- [x] Author `requirements.txt` with pinned versions.
- [x] Author `docker-compose.yml` (Neo4j, Postgres, Redis, API, Streamlit).
- [x] Author `docker/Dockerfile`.
- [x] Author `.env.example` and `.gitignore`.
- [ ] Centralised configuration loader (`app/core/config.py`) using `pydantic-settings`.
- [ ] Logger setup (`app/core/logging.py`) using `loguru`.
- [ ] Document parser (`app/services/parser.py`) supporting PDF, DOCX, TXT with OCR fallback.
- [ ] Clause segmenter (`app/services/segmenter.py`) — regex + heading detection.
- [ ] Text cleaning utilities (`app/utils/text.py`).
- [ ] Unit tests for parser + segmenter (`tests/test_parser.py`, `tests/test_segmenter.py`).

---

## 2. Phase 2 — NLP Core
- [ ] Clause classifier with DeBERTa-v3 (`nlp/clause_classification/classifier.py`).
- [ ] Long-clause chunker using `nlpaueb/legal-bert` sentence splitter.
- [ ] DeBERTa NER model wrapper (`nlp/ner/ner.py`) with regex fallback for CIN/PAN/GSTIN.
- [ ] spaCy rule-based obligation extractor (`nlp/obligation_extraction/extractor.py`).
- [ ] Hybrid LLM-ready interface for obligation extraction (optional later).
- [ ] Unit tests for each NLP module.

---

## 3. Phase 3 — Risk & Graph
- [ ] Indian statutory rule engine (`nlp/risk_scoring/rules_india.py`).
- [ ] Global risk rule engine (`nlp/risk_scoring/rules_global.py`).
- [ ] Risk scoring aggregator (`nlp/risk_scoring/scorer.py`).
- [ ] Neo4j connection manager (`app/db/neo4j.py`) with retry + index bootstrap.
- [ ] Graph write pipeline (`app/services/graph_writer.py`).
- [ ] Cypher queries module (`app/db/queries.py`).

---

## 4. Phase 4 — Backend & UI
- [ ] FastAPI app (`app/main.py`) with lifespan + CORS + exception handlers.
- [ ] Pydantic schemas (`app/models/schemas.py`).
- [ ] Routes (`app/api/routes_contracts.py`, `routes_jobs.py`, `routes_graph.py`).
- [ ] Background task harness (`app/services/jobs.py`).
- [ ] Streamlit `Home.py` (upload page).
- [ ] Streamlit `pages/1_Summary.py`.
- [ ] Streamlit `pages/2_Clause_Explorer.py`.
- [ ] Streamlit `pages/3_Obligations.py`.
- [ ] Streamlit `pages/4_Graph.py`.
- [ ] Streamlit `pages/5_Risk_Review.py`.
- [ ] `streamlit_app/components/risk_card.py`.

---

## 5. Phase 5 — Tests & Hardening
- [ ] End-to-end smoke test (`tests/test_e2e.py`).
- [ ] README with run instructions.
- [ ] Sample contract fixture (`data/raw/sample_msa.txt`).
- [ ] Demo script (`scripts/run_demo.py`).

---

## 6. Architectural Notes (auto-populated)
- 2026-08-18: Chose `pdfplumber` + `PyMuPDF` for primary extraction, `pytesseract` for OCR fallback triggered when < 50 chars on a page.
- 2026-08-18: Chose `microsoft/deberta-v3-base` for both classification and NER with regex fallback to avoid 400MB cold-start blocking the demo.
- 2026-08-18: Risk engine is rule-first; ML risk classifier deferred to post-MVP.
- 2026-08-18: Neo4j used in single-instance mode for MVP; multi-tenant deferred.

---

## 7. Deferred / Post-MVP
- OCR with `surya-ocr` or `docTR` (pytesseract is enough for MVP).
- Hindi / regional language support.
- LLM-based redline generation.
- Case-law link augmentation.
- Workflow approval / Slack / Jira integrations.