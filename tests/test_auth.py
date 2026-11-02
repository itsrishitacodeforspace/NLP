"""Authentication / RBAC tests.

Auth is off by default, so these tests exercise both the open mode and the
enabled mode (by overriding environment variables and clearing the settings
cache).
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    role_allows,
    user_store,
    verify_password,
)

AUTH_ENV = ("AUTH_ENABLED", "AUTH_SECRET_KEY", "AUTH_USERS")


def _client() -> TestClient:
    from app.main import app

    return TestClient(app)


def test_password_hashing_roundtrip():
    hashed = hash_password("s3cret")
    assert hashed != "s3cret"
    assert verify_password("s3cret", hashed)
    assert not verify_password("wrong", hashed)


def test_token_roundtrip_and_role_ranking():
    token, expires_in = create_access_token("alice", "admin")
    assert expires_in > 0
    claims = decode_access_token(token)
    assert claims and claims["sub"] == "alice" and claims["role"] == "admin"
    assert decode_access_token("not-a-token") is None

    assert role_allows("admin", ["viewer"])
    assert role_allows("analyst", ["admin", "analyst"])
    assert not role_allows("viewer", ["admin", "analyst"])


def test_auth_disabled_is_open():
    get_settings.cache_clear()
    user_store.reset()
    client = _client()
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["authenticated"] is False
    # Login is unavailable when auth is off.
    assert client.post("/api/v1/auth/token", data={"username": "x", "password": "y"}).status_code == 400


def test_login_and_role_based_access(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("AUTH_SECRET_KEY", "test-secret")
    monkeypatch.setenv(
        "AUTH_USERS",
        '[{"username": "ana", "password": "pw", "role": "analyst"},'
        ' {"username": "vie", "password": "pw", "role": "viewer"}]',
    )
    get_settings.cache_clear()
    user_store.reset()
    try:
        client = _client()
        payload = {"file": ("c.txt", b"1. Payment\nCustomer shall pay within 30 days.", "text/plain")}

        # No token -> 401 on the protected write route.
        assert client.post("/api/v1/contracts/upload", files=payload).status_code == 401

        # Bad credentials -> 401.
        assert (
            client.post("/api/v1/auth/token", data={"username": "ana", "password": "bad"}).status_code
            == 401
        )

        # Viewer logs in but may not upload -> 403.
        viewer = client.post("/api/v1/auth/token", data={"username": "vie", "password": "pw"}).json()
        assert viewer["role"] == "viewer"
        denied = client.post(
            "/api/v1/contracts/upload",
            files=payload,
            headers={"Authorization": f"Bearer {viewer['access_token']}"},
        )
        assert denied.status_code == 403

        # Analyst logs in and may upload -> 200.
        analyst = client.post("/api/v1/auth/token", data={"username": "ana", "password": "pw"}).json()
        ok = client.post(
            "/api/v1/contracts/upload",
            files=payload,
            headers={"Authorization": f"Bearer {analyst['access_token']}"},
        )
        assert ok.status_code == 200, ok.text

        # Identity lookup reflects the token subject.
        me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {analyst['access_token']}"})
        assert me.json() == {"username": "ana", "role": "analyst", "authenticated": True}
    finally:
        for key in AUTH_ENV:
            monkeypatch.delenv(key, raising=False)
        get_settings.cache_clear()
        user_store.reset()
