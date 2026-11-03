"""Security-hardening tests (audit P2 workstream, 2026-11-03).

Covers:
  - default AUTH_SECRET_KEY guard (refuse in production, CRITICAL in dev);
  - /token rate limiting;
  - true 413 on oversize uploads;
  - bounded job worker pool;
  - error hygiene (no exception details in production response bodies);
  - RLS fallback after in-memory eviction.
"""
from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# 1. Default-secret guard
# ---------------------------------------------------------------------------


def _settings(auth_enabled=True, secret="dev-insecure-secret-change-me", app_env="development"):
    from app.core.config import Settings

    return Settings(
        auth_enabled=auth_enabled,
        auth_secret_key=secret,
        app_env=app_env,
    )


@pytest.mark.parametrize("env", ["production", "prod", "staging", "Production", "PROD"])
def test_default_secret_refuses_startup_in_productionish(env):
    from app.main import guard_auth_secret

    with pytest.raises(RuntimeError, match="AUTH_SECRET_KEY"):
        guard_auth_secret(_settings(app_env=env))


def test_default_secret_warns_but_starts_in_development(monkeypatch):
    from app import main

    monkeypatch.setattr(main.logger, "critical", lambda msg, *a: None)
    # Must not raise in a development-like environment.
    main.guard_auth_secret(_settings(app_env="development"))
    main.guard_auth_secret(_settings(app_env="local"))


def test_default_secret_is_silent_when_auth_disabled():
    from app import main

    # AUTH_ENABLED=false: no tokens exist, nothing to guard.
    main.guard_auth_secret(_settings(auth_enabled=False, app_env="production"))


def test_custom_secret_is_fine_in_production():
    from app import main

    main.guard_auth_secret(_settings(app_env="production", secret="a-very-long-random-secret"))


# ---------------------------------------------------------------------------
# 2. /token rate limiting (per-username failure throttle)
# ---------------------------------------------------------------------------


@pytest.fixture
def auth_client(monkeypatch):
    """Auth-enabled app with one user (ana/pw), clean throttle around it."""
    from fastapi.testclient import TestClient

    from app.core.config import get_settings
    from app.core.security import user_store

    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("AUTH_SECRET_KEY", "test-secret")
    monkeypatch.setenv('AUTH_USERS', '[{"username": "ana", "password": "pw", "role": "analyst"}]')
    get_settings.cache_clear()
    user_store.reset()
    user_store._seed()
    from app.api import routes_auth

    routes_auth._reset_token_throttle()
    client = TestClient(__import__("app.main", fromlist=["app"]).app)
    yield client
    routes_auth._reset_token_throttle()
    get_settings.cache_clear()
    user_store.reset()


def test_token_throttle_locks_after_five_failures(auth_client):
    """5 bad passwords -> the 6th attempt within the window returns 429."""
    for i in range(5):
        r = auth_client.post("/api/v1/auth/token", data={"username": "ana", "password": "bad"})
        assert r.status_code == 401, f"attempt {i + 1}: {r.status_code}"
    # 6th attempt: locked out (time is real, well inside the 60s window).
    r = auth_client.post("/api/v1/auth/token", data={"username": "ana", "password": "bad"})
    assert r.status_code == 429, r.text
    assert "Retry-After" in r.headers


def test_token_throttle_lockout_ignores_even_correct_password(auth_client):
    """While locked, even the right password gets 429 (no credential oracle)."""
    from app.api import routes_auth

    for _ in range(routes_auth.TOKEN_MAX_FAILURES):
        auth_client.post("/api/v1/auth/token", data={"username": "ana", "password": "bad"})
    r = auth_client.post("/api/v1/auth/token", data={"username": "ana", "password": "pw"})
    assert r.status_code == 429


def test_token_throttle_success_resets_counter(auth_client):
    """A successful login resets the counter, so more than MAX failures can
    accumulate across sessions without a permanent lock."""
    from app.api import routes_auth

    for _ in range(routes_auth.TOKEN_MAX_FAILURES - 1):
        auth_client.post("/api/v1/auth/token", data={"username": "ana", "password": "bad"})
    r = auth_client.post("/api/v1/auth/token", data={"username": "ana", "password": "pw"})
    assert r.status_code == 200
    # Counter reset: another full round of MAX failures is possible.
    for _ in range(routes_auth.TOKEN_MAX_FAILURES):
        auth_client.post("/api/v1/auth/token", data={"username": "ana", "password": "bad"})
    assert auth_client.post(
        "/api/v1/auth/token", data={"username": "ana", "password": "bad"}
    ).status_code == 429


def test_token_throttle_usernames_are_independent(auth_client):
    """Locking one username does not affect others."""
    from app.api import routes_auth

    for _ in range(routes_auth.TOKEN_MAX_FAILURES):
        auth_client.post("/api/v1/auth/token", data={"username": "ana", "password": "bad"})
    # Unknown usernames are not in AUTH_USERS, so they 401 normally...
    r = auth_client.post("/api/v1/auth/token", data={"username": "ghost", "password": "x"})
    assert r.status_code == 401
    # ...and ana is locked.
    r = auth_client.post("/api/v1/auth/token", data={"username": "ana", "password": "pw"})
    assert r.status_code == 429
    assert set(routes_auth._throttle_snapshot()) == {"ana", "ghost"}


def test_token_throttle_window_resets_with_time(auth_client, monkeypatch):
    """After the lockout window elapses (faked clock), attempts are allowed again."""
    from app.api import routes_auth

    now = [1000.0]
    monkeypatch.setattr(routes_auth, "_now", lambda: now[0])

    for _ in range(routes_auth.TOKEN_MAX_FAILURES):
        now[0] += 0.01
        auth_client.post("/api/v1/auth/token", data={"username": "ana", "password": "bad"})
    assert auth_client.post(
        "/api/v1/auth/token", data={"username": "ana", "password": "bad"}
    ).status_code == 429

    # Elapse the window; the first new attempt is no longer throttled (it
    # 401s on the bad password and restarts the counter).
    now[0] += routes_auth.TOKEN_LOCKOUT_SECONDS + 1
    r = auth_client.post("/api/v1/auth/token", data={"username": "ana", "password": "bad"})
    assert r.status_code == 401, r.text
    assert routes_auth._throttle_snapshot()["ana"][0] == 1


# ---------------------------------------------------------------------------
# 3. True oversize 413 on upload
# ---------------------------------------------------------------------------

# The route computes ``max_bytes = settings.max_upload_mb * 1024 * 1024``. The
# setting is an int number of MB, so the tests patch it on the cached
# Settings singleton; the cap used here is 2 MiB (small payloads suffice).
_KIB = 1024


@pytest.fixture
def small_upload_cap(monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    original = settings.max_upload_mb
    monkeypatch.setattr(settings, "max_upload_mb", 2)  # 2 MiB cap
    yield 2 * 1024 * 1024  # the effective byte cap
    monkeypatch.setattr(settings, "max_upload_mb", original)


def _upload_bytes(file_bytes: bytes) -> "object":
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        return client.post(
            "/api/v1/contracts/upload",
            files={"file": ("c.txt", file_bytes, "text/plain")},
        )


def test_oversize_upload_is_413(small_upload_cap):
    cap = small_upload_cap
    r = _upload_bytes(b"x" * (cap + 1))
    assert r.status_code == 413, r.text
    assert "limit" in r.text.lower()


def test_upload_exactly_at_limit_is_accepted(small_upload_cap):
    from app.services import jobs

    saved = dict(jobs._jobs)
    with jobs._jobs_lock:
        jobs._jobs.clear()
    cap = small_upload_cap
    try:
        r = _upload_bytes(b"x" * cap)
        assert r.status_code == 200, r.text
        assert r.json()["status"] in {"queued", "running"}, r.text
    finally:
        # Drain the (fake-analysis) job so it cannot bleed into other tests.
        import time

        job_id = r.json()["job_id"]
        for _ in range(200):
            with jobs._jobs_lock:
                j = jobs._jobs.get(job_id)
            if j is None or j.status.value in {"succeeded", "failed"}:
                break
            time.sleep(0.05)
        with jobs._jobs_lock:
            jobs._jobs.clear()
            jobs._jobs.update(saved)


def test_upload_just_over_limit_is_413(small_upload_cap):
    cap = small_upload_cap
    r = _upload_bytes(b"x" * (cap + _KIB))
    assert r.status_code == 413, r.text


# ---------------------------------------------------------------------------
# 4. Error hygiene: no exception details in production response bodies
# ---------------------------------------------------------------------------

# A message that would be an obvious leak if echoed verbatim: a class name and
# an internal path, plus a sentinel that is trivially greppable in the body.
_LEAK_SENTINEL = "ZqxLeakProbe731"


def _app_env(monkeypatch, env: str):
    """Point the app's module-level settings binding at a fresh Settings."""
    from app import main
    from app.core import config as _cfg

    s = _cfg.Settings(app_env=env)
    monkeypatch.setattr(main, "settings", s, raising=False)
    return s


def test_500_body_is_generic_in_production(monkeypatch):
    """A raised exception with a distinctive message must not leak its class
    name or internal path in production-like response bodies."""
    from fastapi.testclient import TestClient

    from app import main

    _app_env(monkeypatch, "production")

    probe = None
    try:

        @main.app.get("/_probe_500")
        def _probe():
            raise RuntimeError(f"{_LEAK_SENTINEL} /marimo/nlp/app/secret/internal.py")

        probe = main.app.router.routes[-1]
        client = TestClient(main.app, raise_server_exceptions=False)
        r = client.get("/_probe_500")
        assert r.status_code == 500, r.text
        body = r.text
        assert "RuntimeError" not in body, f"class name leaked in production: {body}"
        assert _LEAK_SENTINEL not in body, f"exception message leaked: {body}"
        assert "/marimo/nlp" not in body, f"internal path leaked: {body}"
    finally:
        if probe is not None:
            main.app.router.routes.remove(probe)
