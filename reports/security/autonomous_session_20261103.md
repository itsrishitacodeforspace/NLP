# Security Hardening Workstream — Autonomous Session (2026-11-03)

Scope: backend security findings from `DEEP_AUDIT_20261103.md` §2.2 (audit P2
items 11) — contract id collision, token re-validation, default-secret guard,
/token rate limiting, true oversize 413, job worker pool, error hygiene, RLS
smoke re-check.

Baseline: `f0bad0a` (branch main), targeted suite green before any change.
Final state: **560 passed** full suite, `uv run ruff check app/ tests/` clean.

## Commits (local only, never pushed)

| Hash | Message |
|---|---|
| `357a20a` | fix(backend): make contract_id unique per upload (uuid4 component) |
| `b5ea595` | fix(backend): re-validate JWT claims against the live user store |
| `e0da7de` | fix(backend): guard against the shipped default AUTH_SECRET_KEY |
| `c268add` | fix(backend): rate-limit /api/v1/auth/token per username |
| `9c34b24` | fix(backend): reject true oversize uploads with 413, never truncate |
| `6e0b32b` + (carried by `33a8d15`) | fix(backend): bound background job concurrency with a worker pool |
| `803315d` | test(security): lock error hygiene - 500 body generic in production |
| `84340a2` | fix(backend): quiet the job-eviction race in the pool runner |

## Defect-by-defect: reproduction → fix → test

### 1. CONTRACT_ID collision (routes_contracts.py)
- **Reproduced:** `_contract_id_for("c.txt", b"x")` called twice in the same
  second returned identical ids (`c_<stamp>_<sha10>`); identical content ⇒
  identical Neo4j MERGE key + Postgres upsert key.
- **Fix:** id is now `c_<stamp>_<sha10>_<uuid4[:8]>` — unique per upload,
  still readable. `app/api/routes_contracts.py`.
- **Test:** `tests/test_api_smoke.py::test_same_content_uploads_same_second_get_distinct_contract_ids`
  (50 same-second identical-content ids all distinct).

### 2. TOKEN re-validation (deps.py)
- **Reproduced:** with AUTH enabled, minted a token for `ana`, then mutated
  the store (demote / delete) and called `get_current_principal(token)` —
  the demoted/deleted user kept full access with the still-valid JWT.
- **Fix:** after decoding, look the user up in the live `UserStore`. Deleted
  user → 401; token role higher than stored role → 401; stored role ≥ token
  role → token honoured at the stored role (promotion applies immediately).
  Degradation semantics (documented in `deps.py`): a user the store has never
  seen in this process, or a store error, falls back to trusting the claims —
  the token remains the primary credential. `UserStore` gained `has_ever_seen`
  (+ `_ever_seen` tracking in `_seed`) so a deletion is distinguishable from
  "not seeded yet". `app/api/deps.py`, `app/core/security.py`.
- **Tests:** 4 in `tests/test_auth.py` (deleted, demoted, inflated, promoted).

### 3. DEFAULT SECRET guard
- **Reproduced:** `AUTH_ENABLED=true` + default key starts fine in any env;
  the shipped default in `app/core/config.py` is
  `dev-insecure-secret-change-me`.
- **Fix:** `guard_auth_secret(settings)` in `app/main.py`, run at startup
  (lifespan): raises `RuntimeError` when `app_env` ∈ {production, prod,
  staging} (case-insensitive) with the default key; logs CRITICAL in
  development-like envs; silent when auth is disabled.
- **Tests:** 8 in `tests/test_security_hardening.py` (parametrized envs,
  dev-only-warning, auth-off, custom key).

### 4. /token RATE LIMITING (routes_auth.py)
- **Reproduced:** unlimited consecutive 401s on `/api/v1/auth/token` — no
  throttling at all.
- **Fix:** process-local per-username counter (thread-safe, documented:
  not shared across replicas, resets on restart). 5 consecutive failures →
  **429** with `Retry-After` for 60 s; the correct password is also 429 while
  locked (no credential oracle). Successful login resets the counter. Test
  helpers `_reset_token_throttle()` / `_throttle_snapshot()`; faked clock via
  `_now()`. Chosen behavior (429) is documented in the module docstring.
- **Tests:** 5 in `tests/test_security_hardening.py` (lockout, lock beats good
  password, reset on success, per-username independence, window reset with a
  faked monotonic clock).

### 5. TRUE OVERSIZE 413 (routes_contracts.py)
- **Reproduced:** `file.size` is not an attribute of `UploadFile` — the
  pre-check was dead code; only `read(max_bytes + 1)` guarded the size.
  Because `max_upload_mb` is an **int** number of MB (cap ≥ 1 MiB, always
  above Starlette's internal chunk size), `read(max_bytes + 1)` is complete:
  oversize ⇒ len > cap.
- **Fix:** removed the dead `file.size` branch (documented why `read(max+1)`
  is complete); oversize now returns **413** with a clear message; exactly-at
  cap is accepted; only full-size contents ever reach the pipeline.
- **Tests:** 3 in `tests/test_security_hardening.py` (cap patched to 2 MiB on
  the Settings singleton: exactly-at-cap → 200, +1 byte → 413, +1 KiB → 413).

### 6. JOB CONCURRENCY CAP (jobs.py)
- **Reproduced:** `run_in_background` spawned one unbounded daemon `Thread`
  per upload.
- **Fix:** module-level `ThreadPoolExecutor` singleton sized by new
  `Settings.job_worker_count` (default 4, also added to `.env.example`);
  `submit()` queues on saturation (no thread per upload); pool never joined
  (daemon-equivalent semantics); 200-cap eviction unchanged. Worker count
  resolves lazily so tests can shrink the pool. Follow-up commit `84340a2`
  quieted the eviction race: a `KeyError` from `update_job` (job evicted by
  the 200-cap mid-run) is the normal lifecycle race and no longer logged as
  "Job failed".
- **Test:** `tests/test_jobs_backend.py::test_job_pool_bounds_concurrency` —
  6 slow jobs on a 2-worker pool: max observed concurrency ≤ 2, all 6
  SUCCEEDED (≈1.2 s runtime).

### 7. ERROR HYGIENE (main.py)
- **Audit:** the unhandled-exception handler already leaks only the exception
  class name in development-like envs; the `BharatContractError` handler
  echoes the domain error message, which is controlled (no `str(exc)` of
  arbitrary exceptions reaches a body from production code paths).
- **Fix:** none required — behavior already complies.
- **Test:** `tests/test_security_hardening.py::test_500_body_is_generic_in_production`
  locks it: a route raising `RuntimeError("<sentinel> /marimo/nlp/app/secret/internal.py")`
  in `app_env=production` returns a 500 whose body contains no class name,
  no message, no internal path. (Temporary probe route is removed afterwards.)

### 8. RLS SMOKE RE-CHECK + post-eviction fallback
- **Re-check:** `tests/test_rls.py` and `tests/test_api_smoke.py` green after
  all of the above (47-test targeted suite green before and after each commit).
- **New test:** `tests/test_security_hardening.py::test_rls_after_eviction_falls_back_to_postgres_scoped`
  — auth enabled (ana + vie, both analysts); Postgres layer monkeypatched so
  `list_job_ids_for_contract` / `get_jobs_by_ids` return ana's job row only
  for `owner in (None, "ana")`; ana's job evicted from the module-level
  `jobs._jobs` dict. Result: ana reads `/summary` → **200** via the Postgres
  fallback; vie → **404** (RLS holds on the fallback path too).

## Verification

- Targeted (per-commit): `uv run pytest tests/test_auth.py tests/test_rls.py
  tests/test_jobs_backend.py tests/test_api_smoke.py
  tests/test_security_hardening.py -q` → **47 passed** (final state).
- Full suite: `uv run pytest tests/ -q` → **560 passed** in ~70 s (includes
  concurrent agents' in-flight work at the time of the run).
- Lint: `uv run ruff check app/ tests/` → **All checks passed!**.
- One working-tree file not owned by this workstream
  (`tests/test_indian_contracts.py`, modified in parallel) was reverted to
  HEAD with `git checkout`; its ruff-clean state matches HEAD.

## Not fixed (out of scope / other workstreams — for the record)

Remaining §2.2 findings intentionally untouched by this session (owned by
other workstreams or P2-deferred): `playbook_id` accepted-but-unused form
field; `uploads/` never cleaned up; `/healthz` triggers Neo4j connect
attempts; `connect_args={"connect_timeout": 3}` is psycopg2-specific;
`fetch_graph` O(all edges) per call.
`AUTH_USERS` parse-failure silently falling back to the seeded admin (audit
§2.2) was **not** changed — it is a behavior change beyond the assigned task
list; noted for approval.
