# Backend Capability Matrix — BharatContract AI

Derived from the **live** OpenAPI spec (`/openapi.json`, backend v0.1.0) plus a
live exercise of each endpoint on `http://127.0.0.1:8010` (the standard
deployment target is `:8000`; port 8000 is occupied in this environment by an
unrelated LLM proxy, so the backend was run on 8010 for verification).

> **Port note:** the task brief says the backend is on `:8000`. In this
> environment `:8000` serves a different service. The frontend's
> `BACKEND_URL` is configurable (default `http://127.0.0.1:8010`); point it at
> `http://localhost:8000` in the standard deployment.

## Endpoints

| Method | Path | Purpose | Verified |
|---|---|---|---|
| POST | `/api/v1/contracts/upload` | Upload file (multipart: `file`, `contract_type`, `user_role`, `jurisdiction`, `playbook_id`) → returns `JobInfo` | ✅ live (sample_msa → job → succeeded) |
| GET | `/api/v1/contracts/{id}/summary` | `ContractSummary` | ✅ |
| GET | `/api/v1/contracts/{id}/clauses` | `{ clauses: Clause[] }` | ✅ |
| GET | `/api/v1/contracts/{id}/obligations` | `{ obligations: Obligation[] }` | ✅ |
| GET | `/api/v1/contracts/{id}/risks` | `{ risks: RiskFlag[] }` | ✅ |
| GET | `/api/v1/jobs` | `{ jobs: JobInfo[] }` (owner-scoped) | ✅ |
| GET | `/api/v1/jobs/{id}` | `JobInfo` (404 if not found or RLS-scoped-out) | ✅ |
| GET | `/api/v1/graph/{contract_id}` | `{ contract_id, nodes[], edges[] }` (Neo4j, in-memory fallback) | ✅ (fallback, Neo4j down) |
| POST | `/api/v1/auth/token` | Login (form `username`,`password`) → `TokenResponse`. **400 when auth disabled** | ✅ |
| GET | `/api/v1/auth/me` | `UserInfo` (anonymous admin when auth off) | ✅ |
| GET | `/healthz` | status, neo4j, env, auth_enabled, provenance | ✅ |

## Capability matrix (feature → backend reality → frontend behavior)

| Feature | Actual endpoint | Supported | Frontend behavior |
|---|---|---|---|
| Authentication | `POST /auth/token`, `GET /auth/me` | Yes (off by default; `AUTH_ENABLED`) | Implement login/logout + role-aware UI. When auth disabled, `/token` returns 400 — frontend shows "auth disabled" and allows anonymous use. Bearer token (only mechanism). |
| Upload | `POST /contracts/upload` | Yes (PDF/DOCX/TXT/MD, ≤ `MAX_UPLOAD_MB`=25MB) | Implement drag-drop + picker + validation + job handoff. 413 on oversize, 400 on bad extension/empty. |
| Demo | **No dedicated demo endpoint** | **No** | No "Run demo" button that calls a fake endpoint. Instead: the upload flow is the demo path; `data/raw/sample_msa.txt` exists server-side but is NOT exposed by an API, so the frontend cannot fetch it. Documented as a backend gap. |
| Job polling | `GET /jobs/{id}` | Yes (`status`: queued/running/succeeded/failed, `progress` 0–1, `message`) | Poll every 1.5s; stop on terminal status; truthful stage label from `message` (no invented %). `progress` is backend-provided (0.1 parse / 0.7 persist / 0.85 metadata / 1.0 done). |
| Contract retrieval | `GET /contracts/{id}/summary` | Yes | Implement. 409 while processing (retry via job), 404 unknown/RLS. |
| Risk findings | `GET /contracts/{id}/risks` | Yes (`RiskFlag` with evidence spans, case_law, enrichment fields) | Implement full detail panel. |
| Obligations | `GET /contracts/{id}/obligations` | Yes (`Obligation` with subject/counterparty/deadline/frequency/confidence) | Implement tracker (table + timeline + ICS). |
| Graph | `GET /graph/{contract_id}` | Yes (nodes/edges; Neo4j with in-memory fallback) | Implement React Flow. Edge types: HAS_CLAUSE, IMPOSES, TRIGGERS. Node labels: Contract/Clause/Obligation/Risk. |
| Contract comparison | **No comparison endpoint** | **No** | Frontend-only comparison: fetch both contracts' clauses/risks/obligations and diff client-side (jsdiff for text). Accurate because full data is available. Documented as frontend-computed, not backend. |

## Notable backend behaviors (must be honored, not worked around)

1. **`progress` + `message`** on a job are the only pipeline signals. `message`
   values observed: `"Parsing document"`, `"Persisting to graph"`,
   `"Saving metadata"`, `"Done"`, `"Completed"`. The frontend maps these to
   stage labels and does NOT fabricate intermediate steps.
2. **`409` means "still processing" or "analysis failed"** on contract
   sub-resource reads. The frontend polls the job, not the sub-resource.
3. **`404` is overloaded**: unknown contract AND RLS-scoped-out both return 404
   (by design — no existence leak). Frontend shows a single "not found or
   no access" state.
4. **`progress` is coarse** (jumps 0.1→0.7→0.85→1.0). The progress bar shows
   the real value; the stage label communicates what's actually happening.
5. **Auth disabled by default** (`AUTH_ENABLED=false`): every request is an
   anonymous admin. The frontend detects this via `/auth/me`
   (`authenticated:false`) and disables the login UI accordingly.
6. **Roles**: `admin` > `analyst` > `viewer`. Upload requires `admin`/`analyst`
   when auth is on. Reads are allowed for any authenticated role.
7. **Graph** returns `404 "Graph not available"` if there's no result (and the
   contract isn't owned by the caller when auth is on).
8. **Evidence spans** (`char_start`/`char_end`) are offsets into the **cleaned
   clause text** (`Clause.text`), NOT raw file bytes — so the review pane must
   highlight within the clause text it renders, keyed by `clause_id`.
9. **`evidence_status`** values: `direct`, `contextual`, `unverified`,
   `unavailable`. The frontend surfaces the unverified state honestly and never
   presents an unverified legal reference as confirmed.
10. **No CORS by default for `:3000`** — the backend's `CORS_ORIGINS` default is
    `http://localhost:8501` / `http://127.0.0.1:8501` (Streamlit). The frontend
    dev origin must be added (see README). The dev rewrite proxy (`/api` →
    backend) sidesteps CORS entirely in development.
