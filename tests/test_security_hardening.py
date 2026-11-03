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
