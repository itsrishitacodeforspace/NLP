# BharatContract AI — Living Plan & Execution Checklist

> Status: ✅ **Phases 1–6 complete + hardening pass.**
> Last update: 2026-10-22

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
- [x] Author `pyproject.toml` (uv-managed) with optional `[ml]` extra (torch/transformers).
- [x] Author `docker-compose.yml` (Neo4j, Postgres, Redis, API, Streamlit).
- [x] Author `docker/Dockerfile`.
- [x] Author `.env.example`, `.env`, `.gitignore`, `uv.toml`.
- [x] Centralised configuration loader (`app/core/config.py`) using `pydantic-settings`.
- [x] Logger setup (`app/core/logging.py`) using `loguru`.
- [x] Domain exceptions (`app/core/exceptions.py`).
- [x] Document parser (`app/services/parser.py`) supporting PDF, DOCX, TXT with OCR fallback.
- [x] Clause segmenter (`app/services/segmenter.py`) — regex + heading detection + long-clause split.
- [x] Text cleaning utilities (`app/utils/text.py`) with paragraph-preserving whitespace normalisation.
- [x] Filesystem helpers (`app/utils/fs.py`).
- [x] Unit tests for parser + segmenter (`tests/test_parser.py`, `tests/test_segmenter.py`).

---

## 2. Phase 2 — NLP Core
- [x] Clause classifier with DeBERTa-v3 wrapper (`nlp/clause_classification/classifier_ml.py`) — lazy-loaded, optional.
- [x] Rule-based multi-label clause classifier (`nlp/clause_classification/classifier.py`) — primary engine for MVP.
- [x] NER module (`nlp/ner/ner.py`) with regex-first extraction of CIN, PAN, GSTIN, TAN, INR amounts, dates, notice periods, Indian & foreign arbitration seats.
- [x] DeBERTa NER enrichment wrapper (`nlp/ner/ner_ml.py`) — graceful no-op when torch/transformers unavailable.
- [x] spaCy-style obligation extractor (`nlp/obligation_extraction/extractor.py`) — modal-based pattern matching with risk-level derivation.
- [x] Pipeline orchestrator (`app/services/analyzer.py`) tying parser → segmenter → classification → NER → obligations → risk → scoring.

---

## 3. Phase 3 — Risk & Graph
- [x] Indian-statutory risk rules (`nlp/risk_scoring/rules.py`) covering Stamp Duty, Arbitration Seat/Venue mismatch, TDS, Section 124 indemnity, Governing Law mismatch, foreign arbitration seat in domestic contract.
- [x] Global risk rules — uncapped liability, auto-renewal, broad indemnity, one-sided termination, missing clauses, missing data protection.
- [x] Risk scoring aggregator (`nlp/risk_scoring/scorer.py`) with weighted contract score.
- [x] Neo4j connection manager (`app/db/neo4j.py`) with retry-throttling + fast-fail on unavailability + ServiceUnavailable handling.
- [x] Graph write pipeline (`app/db/queries.py`) with idempotent `MERGE` operations and transaction safety.
- [x] Cypher queries — Contract/Clause/Obligation/Risk/Party indexes + contract subgraph fetch.
- [x] PostgreSQL metadata store (`app/db/postgres.py`) with availability cache (no blocking when DB is down).

---

## 4. Phase 4 — Backend & UI
- [x] FastAPI app (`app/main.py`) with lifespan + CORS + exception handlers.
- [x] Pydantic schemas (`app/models/schemas.py`).
- [x] Routes (`app/api/routes_contracts.py`, `routes_jobs.py`, `routes_graph.py`).
- [x] Background job manager (`app/services/jobs.py`) using thread workers + in-memory + DB state.
- [x] Streamlit `Home.py` (upload page) with local-fallback analyser when API is unreachable.
- [x] Streamlit `pages/1_Summary.py` — executive summary with risk badges.
- [x] Streamlit `pages/2_Clause_Explorer.py` — filterable clause list with risk reasons + entity chips.
- [x] Streamlit `pages/3_Obligations.py` — table with CSV export.
- [x] Streamlit `pages/4_Graph.py` — `streamlit-agraph` visualisation with in-memory fallback when Neo4j is unavailable.
- [x] Streamlit `pages/5_Risk_Review.py` — risk review with download.
- [x] `streamlit_app/components/risk_card.py` — risk badge + clause card + header components.

---

## 5. Phase 5 — Tests & Hardening
- [x] End-to-end smoke test (`tests/test_e2e.py`) on bundled sample MSA.
- [x] Unit tests for parser + + segmenter.
- [x] Long-clause splitter tests (`tests/test_long_clauses.py`).
- [x] Hybrid classifier accuracy tests on real CUAD data (`tests/test_classifier_accuracy.py`).
- [x] Live API smoke test (`bash` end-to-end upload → job poll → summary fetch → graph fetch — verified manually, documented in logs).
- [x] Streamlit boot test (HTTP 200 confirmed on `/`).
- [x] README with run instructions.
- [x] Sample contract fixture (`data/raw/sample_msa.txt`).
- [x] Demo script (`scripts/run_demo.py`).

---

## 6. Phase 6 — Real Legal Datasets (Aug 2026)
- [x] Download **CUAD** (Contract Understanding Atticus Dataset, NeurIPS 2021)
      → `data/datasets/cuad/CUADv1.json`, `train_separate_questions.json`, `test.json`, `category_descriptions.csv`.
- [x] Download **MAUD** (Merger Agreement Understanding Dataset, Atticus Project)
      → `data/datasets/maud/data/{MAUD_train,dev,test}.csv` + 152 contract files.
- [x] `nlp/datasets/unified.py` — common `TrainingExample` schema + CUAD/MAUD label mappers.
- [x] `nlp/datasets/cuad.py` — SQuAD-format reader → clause snippets + gold spans.
- [x] `nlp/datasets/maud.py` — CSV reader → clause-type examples.
- [x] `scripts/build_training_data.py` — orchestrator that materialises
      `cuad_examples.jsonl`, `maud_examples.jsonl`, `unified_examples.jsonl`,
      `clause_classifier.csv`, and `cuad_keyword_bank.json`.
- [x] **66,514** unified training rows covering 15 populated internal categories
      (11,508 positive clause-classifier rows after filtering/deduplication).
- [x] `nlp/clause_classification/classifier.py`:
      - Auto-loads CUAD keyword bank on import (top 80 keywords/category).
      - Hybrid pipeline: TF-IDF + Logistic Regression ML model + rule-based fallback.
      - 52.8 % top-1 / 54.2 % top-3 accuracy on CUAD held-out (rule-based: 42.8 %).
- [x] `scripts/train_tfidf_classifier.py` — sklearn pipeline trainer that
      persists to `models/tfidf_classifier.joblib`.
- [x] `scripts/eval_classifier.py` — per-category top-1 accuracy report.

---

## 6. Hardening Pass (2026-10-22)
- [x] Single taxonomy source (`nlp/taxonomy.py`); CUAD/MAUD loaders emit canonical labels.
- [x] MAUD loader rewritten for the real CSV schema; CUAD retains negative examples for the keyword bank.
- [x] Bundled model loader (`nlp/clause_classification/tfidf_model.py`) extracts the 7z archive with `py7zr` and suppresses sklearn version warnings.
- [x] Keyword classifier uses letter-boundary matching; evaluation precision fixed.
- [x] NER: valid CIN/LLPIN/GSTIN regexes, raw-text offsets, seat/venue/law detection.
- [x] Obligations: prohibition/right/obligation precedence, first-modal subject, hours-aware deadlines, descriptive `seat/venue/governed` sentences ignored.
- [x] Risk playbook: contract-level Indian rules execute, auto-renewal context, breach hours, liability-cap guard, arbitration mismatch guards.
- [x] Backend: JSON-safe job persistence, DB fallbacks, bounded in-memory jobs, upload size pre-check, Neo4j lazy availability, unique graph IDs, strict CORS defaults.
- [x] Docker: correct build context, project install, `.dockerignore`, healthchecks, ordered startup, renderer/UI fixes.
- [x] Regression tests for obligation subjects and job serialisation; full pytest + ruff pass.

---

## 7. Architectural Notes (auto-populated)
- 2026-08-18: Chose `pdfplumber` (primary) + `PyMuPDF` (fallback) + `pytesseract` (OCR fallback triggered when < 50 chars on a page).
- 2026-08-18: Chose `microsoft/deberta-v3-base` for both classification and NER — wrapped behind lazy import so the stack runs without ML deps. Regex fallback covers CIN/PAN/GSTIN/dates.
- 2026-08-18: Risk engine is rule-first; ML risk classifier deferred to post-MVP.
- 2026-08-18: Neo4j used in single-instance mode for MVP. Connection attempts are throttled to once every 10s when failing — keeps pipeline responsive without retry storms.
- 2026-08-18: Postgres connection is probed once at engine init; subsequent calls fast-fail via `_AVAILABLE_CACHE` so job runtime stays < 1s when DB is down.
- 2026-08-18: Party detection uses NER + suffix-based regex fallback with noise-word stripping (handles "between X and Y" preamble pattern common in MSA preambles).
- 2026-08-18: Streamlit graph page has in-memory fallback that reconstructs the graph from the AnalysisResult when Neo4j is unavailable — so the demo works without external infra.

---

## 8. Deferred / Post-MVP
- OCR with `surya-ocr` or `docTR` (pytesseract is enough for MVP).
- Hindi / regional language support (Indic-BERT / MuRIL).
- LLM-based redline generation (Llama-3 / Qwen).
- Case-law link augmentation.
- Workflow approval / Slack / Jira integrations.
- ML-driven risk classifier (today is rule-only).
- Per-user authentication & row-level security in Postgres.