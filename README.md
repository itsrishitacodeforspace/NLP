# BharatContract AI

> Automated detection of dangerous clauses, missing stamp duties, arbitration risks, and hidden obligations in Indian and global legal contracts — *before you sign*.

---

## What it does

1. **Upload** any contract (PDF, DOCX, TXT).
2. **Parse** with OCR fallback for scanned documents.
3. **Segment** clauses using rule-based heading detection.
4. **Classify** each clause (DeBERTa-v3 + rule fallback).
5. **Extract** entities (parties, dates, CIN, PAN, GSTIN, jurisdictions, notice periods, liability caps).
6. **Detect obligations** (subject / action / object / deadline).
7. **Score risk** with an Indian-statutory-aware playbook (Stamp Duty, Arbitration Seat vs. Venue, TDS, Governing Law mismatch).
8. **Persist** the full picture in **Neo4j** (graph) + **PostgreSQL** (metadata).
9. **Visualise** in a Streamlit dashboard with summary, clause explorer, obligation tracker, and graph view.

## Quick start

```bash
uv sync --extra dev                  # creates .venv + installs everything
uv run python -m spacy download en_core_web_sm
docker compose -f docker/docker-compose.yml up -d neo4j postgres redis
uv run uvicorn app.main:app --reload
uv run streamlit run streamlit_app/Home.py
```

## Repo layout

```
app/                  FastAPI backend
  api/                routes
  core/               config, logging, exceptions
  db/                 Neo4j connection + Cypher queries
  models/             Pydantic schemas
  services/           parser, segmenter, NLP orchestration
  utils/              text + filesystem helpers
streamlit_app/        Dashboard
nlp/                  clause classification, NER, obligation extractor, risk rules
data/                 raw / processed / templates / playbooks
tests/                unit + integration tests
docker/               Dockerfile + docker-compose.yml
scripts/              demo + bootstrap scripts
```

## Architecture

See `plan.md` for the full architectural source of truth.

## Disclaimer

This tool provides automated contract analysis for **informational purposes only**.
It does not constitute legal advice. Critical contracts should be reviewed by a qualified attorney.