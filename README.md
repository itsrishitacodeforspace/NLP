# BharatContract AI

> Automated detection of dangerous clauses, missing stamp duties, arbitration risks, and hidden obligations in Indian and global legal contracts — **before you sign**.

![Python](https://img.shields.io/badge/python-3.10%E2%80%933.12-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688) ![Streamlit](https://img.shields.io/badge/Streamlit-1.31-FF4B4B) ![Neo4j](https://img.shields.io/badge/Neo4j-5.18-018bff)

---

## What it does

BharatContract AI is an end-to-end contract intelligence platform tuned for the **Indian legal context** while remaining useful for global cross-border agreements.

1. **Upload** any contract (PDF, DOCX, TXT). OCR fallback for scanned PDFs.
2. **Segment** clauses using rule-based heading detection.
3. **Classify** each clause (rule-based + TF-IDF, optional DeBERTa-v3).
4. **Extract entities** (parties, dates, **CIN/PAN/GSTIN**, INR amounts, notice periods, jurisdictions, arbitration seats).
5. **Detect obligations** (subject / action / object / deadline) using modal-verb pattern matching.
6. **Score risk** with an Indian-statutory-aware playbook:
   - Stamp Duty (Indian Stamp Act, 1899)
   - Arbitration Seat vs. Venue mismatch (*BALCO*, *BGS SGS*)
   - Section 124 indemnity gap (Indian Contract Act)
   - Foreign governing law in a domestic contract
   - TDS / GST compliance signals
   - Plus global playbook: uncapped liability, auto-renewal, broad indemnity, one-sided termination, missing mandatory clauses.
7. **Persist** the full picture in **Neo4j** (graph) + **PostgreSQL** (metadata).
8. **Visualise** in a Streamlit dashboard with summary, clause explorer, obligation tracker, risk review, and graph view.

---

## Quick start

```bash
# 1. Install (uses uv — pinned versions, hardlink-safe on OneDrive)
uv sync --extra dev

# 2. (Optional) download the spaCy English model
uv run python -m spacy download en_core_web_sm

# 3. Bring up infra (or run the whole stack with `up --build`)
docker compose -f docker/docker-compose.yml up -d neo4j postgres redis

# 4. Start the API
uv run uvicorn app.main:app --reload

# 5. In a second terminal, start the dashboard
uv run streamlit run streamlit_app/Home.py
```

Then open:
- API: http://localhost:8000/docs
- Dashboard: http://localhost:8501

A bundled sample MSA lives in `data/raw/sample_msa.txt`. From the dashboard's Home page, click **Run demo analysis on bundled sample MSA** to see the pipeline without uploading anything.

---

## CLI demo (no infra required)

```bash
uv run python scripts/run_demo.py
```

Prints a JSON summary of the bundled sample: parties, dates, governing law, arbitration seat, top risks, clause & obligation counts.

---

## Repository layout

```
app/                          FastAPI backend
  api/                        routes (contracts, jobs, graph)
  core/                       config, logging, exceptions
  db/                         graph + SQL adapters
  models/                     Pydantic schemas
  services/                   parser, segmenter, analyzer, jobs
  utils/                      text + filesystem helpers
nlp/                          NLP modules
  clause_classification/      rule-based + TF-IDF classifier
  ner/                        regex-first NER + optional DeBERTa enrichment
  obligation_extraction/      modal-verb pattern extractor
  risk_scoring/               rule engine + aggregator
streamlit_app/                Dashboard
  pages/                      1_Summary, 2_Clause_Explorer, ...
  components/                 risk_card, clause_card, header
data/                         raw / processed
docker/                       Dockerfile + docker-compose.yml
scripts/                      run_demo.py
tests/                        unit + integration tests
uploads/                      uploaded files (gitignored)
models/                       bundled TF-IDF archive + local cache
logs/                         runtime logs
```

---

## Architecture

```
Streamlit UI ──┐
               │ REST (httpx)
FastAPI API ───┤
               │
   ┌───────────┼───────────┐
   │           │           │
Document    Inference    Graph
Parser       Pipeline    Queries
   │           │           │
   ▼           ▼           ▼
┌────────────────────────────────┐
│  Core processing layer         │
│  1. pdfplumber / PyMuPDF / OCR │
│  2. Regex segmenter            │
│  3. Rule + TF-IDF classifier   │
│  4. Regex-first NER            │
│  5. Modal-verb obligations     │
│  6. Indian + global rule engine│
└────────────────────────────────┘
        │                       │
        ▼                       ▼
   PostgreSQL                Neo4j
   (metadata, jobs)     (Contract → Clause
                          → Obligation → Risk)
```

---

## Environment variables

Copy `.env.example` to `.env` and fill in real values. The defaults are local-development friendly.

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis URL for future Celery workers |
| `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` | Neo4j credentials |
| `CLAUSE_MODEL` / `NER_MODEL` | HF model names |
| `UPLOAD_DIR` | Where uploaded contracts are persisted |
| `MAX_UPLOAD_MB` | Upload size cap |
| `CORS_ORIGINS` | JSON list of allowed browser origins |
| `ENABLE_OCR_FALLBACK` | Auto OCR when <50 chars/page |

---

## Running without external services

The pipeline is engineered to **degrade gracefully**:

- **No Neo4j?** Writes log a warning; the dashboard graph page rebuilds the graph from the in-memory `AnalysisResult`.
- **No Postgres?** Job & contract metadata writes become no-ops (cached after first failed probe).
- **No torch/transformers?** Rule-based classifier, regex NER, and the bundled TF-IDF model still work; DeBERTa enrichment is a silent no-op.
- **No OCR?** pdfplumber + PyMuPDF text extraction still works on digital PDFs.

You can run the entire demo (FastAPI + Streamlit + bundled sample) with **zero infra** other than Python.

---

## Tests

```bash
uv run pytest -v
```

Covers parser, segmenter, long-clause splitting, classifier regression thresholds on CUAD, obligation/job regressions, and the end-to-end pipeline against the bundled sample MSA.

---

## Disclaimer

This tool provides automated contract analysis for **informational purposes only**.
It does not constitute legal advice. Critical contracts should be reviewed by a qualified attorney.

---

## License

Internal use. See `plan.md` for the architectural source of truth.