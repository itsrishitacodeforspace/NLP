# BharatContract AI — Frontend

Legal contract intelligence for Indian commercial contracts. Upload a
PDF/DOCX/TXT/Markdown contract; the FastAPI backend parses, segments and
risk-scores it in the background while you watch live job progress.

> **Mandatory disclaimer:** AI-generated contract analysis is for
> informational purposes only and does not constitute legal advice. Findings
> require appropriate human review.

## Tech stack

| Layer            | Choice                                            |
|------------------|---------------------------------------------------|
| Framework        | **Next.js 14.2 (App Router)**, React 18.3, TypeScript 5.4 |
| Styling          | Tailwind CSS 3.4 + `clsx` + `tailwind-merge` (`cn` helper) |
| Data fetching    | TanStack Query v5 (retry policy: GETs only, no retry on 4xx except 408/429) |
| State            | React hooks; zustand available for future use     |
| Forms            | react-hook-form (login)                           |
| Charts / graph   | recharts (severity bars), `@xyflow/react` (clause graph) |
| Diffing          | `diff` (a.k.a. jsdiff — client-side contract comparison) |
| Icons            | lucide-react                                      |
| Validation       | zod (runtime schemas in `src/lib/validation/`)    |
| Testing          | vitest + @testing-library/react (unit/component), Playwright (e2e) |
| API types        | `openapi-typescript` (generated `src/types/api.ts`) |

**Package manager: `npm`** (this project is set up with `npm install` and
`package-lock.json`; pnpm is not established). Node ≥ **18.17**
(`package.json` `engines`).

## Layout

```
frontend/
├── e2e/                     # Playwright specs (smoke + opt-in live backend)
├── src/
│   ├── app/                 # Next.js App Router pages (/, /login, /jobs/...)
│   ├── components/          # ui/* (design system), layout/*, feature components
│   ├── features/            # per-domain hooks + logic (auth, jobs, risks, ...)
│   ├── lib/
│   │   ├── api/             # fetch client, ApiError, token store
│   │   ├── validation/      # zod runtime schemas (additive, not wired into client)
│   │   ├── severity.ts      # severity ordering/labels/colors
│   │   ├── format.ts        # datetime + job stage labels
│   │   ├── constants.ts     # accepted extensions, contract types, party sides
│   │   └── utils.ts         # cn()
│   ├── test/                # vitest setup + renderWithProviders helper
│   └── types/               # generated api.ts + re-exports
├── tests/                   # component/integration tests (vitest, jsdom)
├── openapi.json             # backend spec (gitignored; regenerate — see below)
├── vitest.config.ts
├── playwright.config.ts
└── next.config.mjs          # dev rewrite: /api → BACKEND_URL
```

## Installation

```bash
cd frontend
npm install
```

## Environment variables

Copy the example file, then adjust as needed:

```bash
cp .env.example .env.local
```

| Variable            | Default                  | Purpose |
|---------------------|--------------------------|---------|
| `BACKEND_URL`       | `http://127.0.0.1:8010`  | Base URL of the FastAPI backend (no trailing slash). Used by the dev rewrite proxy in `next.config.mjs`. |
| `AUTH_ENABLED`      | `false`                  | Mirror of the backend flag; when `true` the login form is offered. The backend is authoritative — the frontend discovers the real state via `GET /api/v1/auth/me`. |
| `AUTH_STORAGE_KEY`  | `bharatcontract.token`   | `localStorage` key for the bearer token. **Do not rename casually** — stored sessions break. |

## Backend startup

The frontend talks to the FastAPI backend in `../` (the repo root).

```bash
cd /marimo/nlp
uv sync --extra dev
uv run uvicorn app.main:app --port 8000 --reload
```

The frontend expects the backend at `BACKEND_URL`. In this environment port
8000 is occupied by an unrelated proxy, so the backend runs on **8010**
(matching the `.env.example` default); in a standard deployment use 8000 and
set `BACKEND_URL=http://localhost:8000`.

> Note: the API paths are versioned — the real routes live under
> `/api/v1/...` (see `openapi.json`).

## API client generation

`src/types/api.ts` is generated from the backend OpenAPI spec:

```bash
# 1. Refresh the spec from a running backend (writes frontend/openapi.json):
curl -s http://127.0.0.1:8010/openapi.json -o frontend/openapi.json

# 2. Regenerate the TS types:
npm run generate:api
```

`openapi.json` is gitignored; commit only the generated
`src/types/api.ts` after regenerating.

## Development server

```bash
npm run dev          # → http://localhost:3000
```

## CORS configuration

**In development you do NOT need to touch CORS.** `next.config.mjs` adds a
rewrite proxy: every browser request to `/api/...` on `:3000` is forwarded
server-side to `${BACKEND_URL}/api/...`. The browser only ever sees a
same-origin request, so no CORS headers are involved.

If you instead call the backend **cross-origin directly** (e.g. you set
`BACKEND_URL` and disable the rewrite, or run the UI on a different host),
the backend must allow your origin via `CORS_ORIGINS`.

- The backend's `CORS_ORIGINS` default is
  `http://localhost:8501,http://127.0.0.1:8501` (the Streamlit dashboard).
  It does **not** include `:3000`.
- **`localhost` and `127.0.0.1` are DIFFERENT origins.** If your browser is
  navigating to `http://localhost:3000`, you must add that exact origin —
  `http://127.0.0.1:3000` will not match, and vice versa.

```bash
# Backend env (the user makes this change; the frontend does NOT modify
# backend config):
CORS_ORIGINS='["http://localhost:3000","http://localhost:8501"]'
```

## Authentication setup

- Backend: `AUTH_ENABLED=false` by default (everyone is an anonymous admin).
  Enable with `AUTH_ENABLED=true` plus `AUTH_USERS` (JSON of
  username → password/role entries; roles are `admin` > `analyst` > `viewer`).
- Login: `POST /api/v1/auth/token` (form `username`,`password`) returns a
  bearer token. The token is stored in `localStorage` under `AUTH_STORAGE_KEY`
  and attached as `Authorization: Bearer <token>` by the API client.
- **Documented trade-off:** `localStorage` is readable by page JavaScript
  (XSS risk). The backend remains authoritative for authorization; frontend
  role checks are **UX only** (showing/hiding the login form, gating buttons)
  and must never be relied on for security. A cookie + CSRF scheme would be
  the production hardening; the backend does not currently support
  `Set-Cookie` auth.
- **401 handling:** any 401 (except on the login call itself) dispatches the
  `bharatcontract:unauthorized` window event; the auth provider clears the
  stored token on a failed `/me`.
- With auth **disabled**, `/auth/me` reports `authenticated: false` and the
  UI shows an "Auth off" status.

## Production build

```bash
npm run build     # type-checks + compiles all pages
npm start         # serves the production build on :3000
```

## Testing

```bash
npm test                      # vitest run — unit + component (jsdom), fast, no backend needed
RUN_REAL_BACKEND=1 npm test   # ALSO runs live backend tests (tests/real-backend.test.ts)
npm run e2e                   # Playwright (dev server started automatically)
```

**Mocked vs real-backend tests**

- `src/**/__tests__/*` — pure unit tests of lib/feature code. No network.
- `tests/*` — component/integration tests in jsdom. The API layer and
  `next/navigation` are mocked where relevant; each mocked file says so in a
  header comment ("MOCKED — does not hit the real backend").
- `tests/real-backend.test.ts` — **not** mocked. Opt-in via
  `RUN_REAL_BACKEND=1` (and `RUN_REAL_BACKEND_JOBS=1` for the upload→pipeline
  tests, which are slower). A pass here genuinely exercises the live backend;
  without the flag it is skipped so the default suite stays green with no
  infrastructure.
- `e2e/smoke.spec.ts` — Playwright, backend-independent (landing page).
  `e2e/backend.spec.ts` — opt-in via `RUN_E2E_BACKEND=1`.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| "Cannot reach the backend" on upload or job list | Backend not running, or `BACKEND_URL` wrong. Check `curl $BACKEND/healthz`. |
| Port 3000 / 8000 already in use | Pick another port and update `BACKEND_URL` / `npm run dev -p`. In this env, :8000 is an unrelated proxy — use :8010. |
| Upload works but UI says "auth disabled" after enabling auth | The frontend discovers auth state from `/auth/me` on load — hard-refresh after changing backend env. |
| **409** on reading a contract's summary/risks/obligations | The analysis is still running (or failed). The UI should poll the **job**, not the sub-resource; a 409 means "try the job". |
| **404** on a contract you just uploaded | 404 is overloaded: unknown ID **and** row-level-security scoped-out both return 404 (by design, no existence leak). With auth on, check the owner. |
| **413** on upload | File exceeds `MAX_UPLOAD_MB` (25 MB default). |
| CORS errors in the browser console | You are bypassing the dev rewrite. Add your exact origin to the backend's `CORS_ORIGINS` (see §CORS) — remember `localhost` ≠ `127.0.0.1`. |

## Known backend capability limitations

From `CAPABILITY_MATRIX.md` (verified against the live OpenAPI spec):

- **No demo endpoint.** There is no "run demo" API; the upload form is the
  demo path. The sample file `data/raw/sample_msa.txt` is NOT exposed by the
  API, so the frontend cannot fetch it.
- **No comparison endpoint.** Contract comparison is computed **client-side**
  (fetch both contracts' data and diff with the `diff`/jsdiff package).
- **Graph fallback.** `GET /graph/{contract_id}` uses Neo4j when available;
  with Neo4j down it returns an in-memory fallback snapshot.
- **Progress is coarse.** Job `progress` jumps 0.1 → 0.7 → 0.85 → 1.0. The UI
  shows the real value plus a truthful stage label from `message`; it never
  invents intermediate percentages.
- **404 is overloaded** (unknown vs RLS-scoped-out — see Troubleshooting).
- **Evidence spans** (`char_start`/`char_end`) are offsets into the **cleaned
  clause text**, not raw file bytes — the review pane highlights within the
  clause text, keyed by `clause_id`.
- **Unverified legal references.** `evidence_status` may be `unverified` /
  `unavailable` / `contextual`; the UI surfaces that honestly and never
  presents an unverified reference as confirmed.

## Security

- No backend secrets (DB URLs, signing keys) ever appear in client env or
  bundle code.
- The bearer token in `localStorage` is a known, documented trade-off
  (see §Authentication).
- **Do not log JWTs** — the API client never logs request headers, and error
  messages surface only the backend `detail` string.

## Accessibility

Full pass results and the small fixes made are documented in
[`TESTING.md`](./TESTING.md) §Accessibility. Summary: focus-visible rings are
present across the design system; icon-only buttons carry `aria-label`s;
state/alert components use `role="alert"` / `role="status"`; the risk gauge
svg exposes `role="img"` + `aria-label`; form controls are label-associated.
One fix applied in this pass: `ErrorState` now carries `role="alert"`
(`src/components/ui/state.tsx`).
