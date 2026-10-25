"""Row-level security tests: a user only sees the contracts/jobs they uploaded."""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.security import user_store

AUTH_ENV = ("AUTH_ENABLED", "AUTH_SECRET_KEY", "AUTH_USERS")


def _login(client: TestClient, username: str, password: str) -> dict:
    r = client.post("/api/v1/auth/token", data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _upload_and_wait(client: TestClient, headers: dict) -> tuple[dict, dict]:
    payload = {
        "file": (
            "c.txt",
            b"1. Payment Terms\nCustomer shall pay Provider within 30 days of invoice.",
            "text/plain",
        )
    }
    r = client.post("/api/v1/contracts/upload", files=payload, headers=headers)
    assert r.status_code == 200, r.text
    job = r.json()
    for _ in range(200):
        done = client.get(f"/api/v1/jobs/{job['job_id']}", headers=headers).json()
        if done["status"] in {"succeeded", "failed"}:
            return job, done
        time.sleep(0.1)
    raise AssertionError("job did not finish in time")


@pytest.fixture
def auth_enabled(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("AUTH_SECRET_KEY", "test-secret")
    monkeypatch.setenv(
        "AUTH_USERS",
        '[{"username": "ana", "password": "pw", "role": "analyst"},'
        ' {"username": "vie", "password": "pw", "role": "viewer"}]',
    )
    get_settings.cache_clear()
    user_store.reset()
    yield
    for key in AUTH_ENV:
        monkeypatch.delenv(key, raising=False)
    get_settings.cache_clear()
    user_store.reset()


def test_contracts_are_scoped_to_their_owner(auth_enabled):
    from app.main import app

    client = TestClient(app)
    ana = _login(client, "ana", "pw")
    vie = _login(client, "vie", "pw")

    job, done = _upload_and_wait(client, ana)
    assert done["status"] == "succeeded"
    assert job["owner"] == "ana"
    cid = job["contract_id"]

    # The owner can read every artefact.
    assert client.get(f"/api/v1/contracts/{cid}/summary", headers=ana).status_code == 200
    assert client.get(f"/api/v1/contracts/{cid}/clauses", headers=ana).status_code == 200
    assert client.get(f"/api/v1/contracts/{cid}/risks", headers=ana).status_code == 200
    assert client.get(f"/api/v1/graph/{cid}", headers=ana).status_code == 200

    # Another user gets 404 (not 403) so the contract's existence is not leaked.
    assert client.get(f"/api/v1/contracts/{cid}/summary", headers=vie).status_code == 404
    assert client.get(f"/api/v1/contracts/{cid}/obligations", headers=vie).status_code == 404
    assert client.get(f"/api/v1/graph/{cid}", headers=vie).status_code == 404
    assert client.get(f"/api/v1/jobs/{job['job_id']}", headers=vie).status_code == 404


def test_job_listing_is_scoped_per_user(auth_enabled):
    from app.main import app

    client = TestClient(app)
    ana = _login(client, "ana", "pw")
    vie = _login(client, "vie", "pw")

    job, _ = _upload_and_wait(client, ana)

    ana_jobs = client.get("/api/v1/jobs", headers=ana).json()["jobs"]
    vie_jobs = client.get("/api/v1/jobs", headers=vie).json()["jobs"]

    assert any(j["job_id"] == job["job_id"] for j in ana_jobs)
    assert all(j["owner"] == "ana" for j in ana_jobs)
    assert all(j["job_id"] != job["job_id"] for j in vie_jobs)
    assert all(j["owner"] == "vie" for j in vie_jobs)
