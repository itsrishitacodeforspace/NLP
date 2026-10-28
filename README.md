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
   - Each finding carries **statutory / case-law pointers** (Indian Stamp Act ss. 33 & 35, *BALCO*, *BGS SGS Soma*, Contract Act ss. 124–125, DPDP Act 2023, …).
   - A **weakly-supervised ML risk classifier** acts as a recall booster for clauses the rules miss.
7. **Persist** the full picture in **Neo4j** (graph) + **PostgreSQL** (metadata).
8. **Authenticate** optionally with JWT bearer tokens and role-based access (`admin` / `analyst` / `viewer`).
9. **Visualise** in a Streamlit dashboard with summary, clause explorer, obligation tracker, risk review, and graph view.

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

> **`data/processed/` is generated, not shipped.** A fresh clone runs out of the box via the bundled
> `models/tfidf_classifier.7z`, but it has no evaluation corpus: the rule-based classifier loses its CUAD
> keyword bank and the accuracy/provenance tests are skipped. To regenerate the corpus from the bundled
> CUAD/MAUD datasets (train-only, with manifests):
>
> ```bash
> uv run python scripts/build_training_data.py   # writes data/processed/* with manifests
> uv run python scripts/verify_provenance.py     # exit 0 when the regenerated artifacts verify
> ```
>
> Set `BCC_EVAL_MODE=ci` when running pytest to make a missing corpus a hard failure instead of a skip.

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
  api/                        routes (auth, contracts, jobs, graph) + deps
  core/                       config, logging, exceptions, time, security
  db/                         graph + SQL adapters
  models/                     Pydantic schemas
  services/                   parser, segmenter, analyzer, jobs
  utils/                      text + filesystem helpers
nlp/                          NLP modules
  clause_classification/      rule-based + TF-IDF classifier
  ner/                        regex-first NER + optional DeBERTa enrichment
  obligation_extraction/      modal-verb pattern extractor
  risk_scoring/               rule engine + aggregator + case-law + ML risk model
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
| `AUTH_ENABLED` | Require JWT bearer tokens (default `false`) |
| `AUTH_SECRET_KEY` | HMAC secret used to sign access tokens |
| `AUTH_TOKEN_EXPIRE_MINUTES` | Access-token lifetime (default 60) |
| `AUTH_ADMIN_PASSWORD` | Password for the seeded `admin` user |
| `AUTH_USERS` | Optional JSON list of `{username, password, role}` users |

---

## API authentication (optional)

Auth is **off by default** so the demo needs zero configuration. Turn it on to
require bearer tokens on the upload route:

```bash
export AUTH_ENABLED=true
export AUTH_SECRET_KEY="a-long-random-secret"
export AUTH_USERS='[{"username":"ana","password":"s3cret","role":"analyst"}]'
uv run uvicorn app.main:app
```

```bash
# Obtain a token
curl -s -X POST http://localhost:8000/api/v1/auth/token \
  -d "username=ana&password=s3cret"
# -> {"access_token":"...","token_type":"bearer","expires_in":3600,...}

# Call a protected route
curl -s -H "Authorization: Bearer <token>" \
  -F "file=@data/raw/sample_msa.txt" \
  http://localhost:8000/api/v1/contracts/upload
```

Roles are ranked `viewer < analyst < admin`; `POST /api/v1/contracts/upload`
needs `analyst` or above. Passwords are hashed with bcrypt (stdlib PBKDF2
fallback); tokens are HS256 JWTs. If `AUTH_USERS` is not set and auth is
enabled, an `admin` account is seeded from `AUTH_ADMIN_PASSWORD` with a warning.

When auth is enabled the API also enforces **row-level security**: a user only
sees the contracts and jobs they uploaded (others return `404`, so existence is
not leaked).

---

## ML risk classifier (optional)

Alongside the rule playbook, `nlp/risk_scoring/risk_model.py` exposes a
**weakly-supervised** TF-IDF + Logistic Regression severity classifier. Its
labels are generated offline by the rule engine itself, so the model mainly
generalises to phrasings the rules do not encode; it is applied only as a
*recall booster* for clauses with no rule hit, emitting an explainable
`ML_RISK_001` finding.

A pre-trained artefact is bundled at `models/risk_classifier.7z` (extracted on
first use). To retrain it:

```bash
uv run python scripts/train_risk_classifier.py --limit 6000
```

Everything degrades to a no-op if the artefact is absent.

---

## Provenance (data lineage)

Generated artifacts under `data/processed/` carry an `<artifact>.manifest.json` recording the source
files with their SHA-256 and split identity, the build command, the code revision and the artifact hash.
Source identity is **hash-pinned** against an allowlist (`nlp/datasets/splits.py`); those hashes were
computed locally and validated only by *internal* partition consistency, so they are **not authenticated
against the upstream CUAD release** (`upstream_authenticated: false`).

```bash
uv run python scripts/verify_provenance.py   # exit 0 only when every artifact verifies
```

**CI/release policy:** this readiness check must exit 0 before a release. On a checkout whose
`data/processed/` predates provenance it exits 1 and reports the missing manifests — an honest
"not verified", never a pass. **The current artefacts are not verified.**

`/healthz` exposes a machine-readable `provenance` block, and analysis warnings carry
`PROVENANCE_UNVERIFIED[artifact=…]` / `PROVENANCE_ABSENT[artifact=…]` tokens. Loaded model status is tied
to the exact `.joblib` bytes executed, with archive/cache hashes and drift detection.

**Three distinct things — do not conflate:** *artifact provenance* (where the bytes came from) ≠
*evaluation* (metrics on a held-out, family-grouped set) ≠ *predictive validity* (real-world correctness).
A manifest proves only the first. Both bundled `models/*.7z` are marked `provenance-unverified` in
`models/PROVENANCE_STATUS.json` because they were trained on a corpus that overlaps the held-out CUAD
documents; no leakage-free or generalization claim is made for them, and any accuracy figure computed on
`data/processed/clause_classifier.csv` is **training-overlapping**.

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

Covers parser, segmenter, long-clause splitting, classifier regression thresholds on CUAD, obligation/job regressions, case-law pointers, authentication/RBAC, and the end-to-end pipeline (plus a live API round-trip) against the bundled sample MSA.

---

## Disclaimer

This tool provides automated contract analysis for **informational purposes only**.
It does not constitute legal advice. Critical contracts should be reviewed by a qualified attorney.

---

## License

Internal use. See `plan.md` for the architectural source of truth.