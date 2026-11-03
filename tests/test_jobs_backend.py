"""Regression tests for the job-persistence / job-listing backend fixes (audit C8/C9).

Covers, without requiring a live Postgres:
  (a) the ``_persist`` payload carries ``created_at`` / ``finished_at``;
  (b) ``list_jobs`` merges the in-memory mirror with Postgres and dedups;
  (c) ``_latest_job_for`` finds an evicted job via the DB path;
  (d) a runner that dies with a ``BaseException`` ends FAILED, not RUNNING;
  (e) a corrupt stored result yields a warning + a non-404 response;
  (f) a FAILED job yields 409 with the error message;
  (g) ``get_engine`` does not double-initialise under two threads;
  (h) a once-down Postgres is re-probed after the bounded window.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Optional

import pytest
from fastapi.testclient import TestClient

from app.db import postgres
from app.models.schemas import (
    AnalysisResult,
    ContractSummary,
    JobInfo,
    JobStatus,
)
from app.services import jobs

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_result(contract_id: str = "c1") -> AnalysisResult:
    return AnalysisResult(
        contract=ContractSummary(
            contract_id=contract_id,
            title="T",
            file_name="f.txt",
            analyzed_at=datetime(2026, 10, 22, 12, 0, 0),
        )
    )


@pytest.fixture
def clear_memory_jobs():
    """Isolate the in-memory job mirror around a test."""
    saved = dict(jobs._jobs)
    with jobs._jobs_lock:
        jobs._jobs.clear()
    yield
    with jobs._jobs_lock:
        jobs._jobs.clear()
        jobs._jobs.update(saved)


def _pg_record(
    job_id: str,
    *,
    contract_id: str = "c1",
    owner: str = "",
    status: str = "succeeded",
    result: Optional[dict] = None,
    error: str = "",
    created_at: Optional[str] = None,
    finished_at: Optional[str] = None,
) -> dict:
    return {
        "job_id": job_id,
        "contract_id": contract_id,
        "owner": owner,
        "status": status,
        "progress": 1.0,
        "message": "Done",
        "result": result if result is not None else _make_result(contract_id).model_dump(mode="json"),
        "error": error,
        "created_at": created_at or "2026-10-22T12:00:00",
        "finished_at": finished_at or "2026-10-22T12:05:00",
    }


# ---------------------------------------------------------------------------
# (a) _persist payload carries created_at / finished_at
# ---------------------------------------------------------------------------


def test_persist_payload_includes_timestamps(monkeypatch, clear_memory_jobs):
    captured: list[dict] = []
    monkeypatch.setattr(jobs, "upsert_job", captured.append)

    now = datetime(2026, 10, 22, 12, 0, 0)
    info = JobInfo(
        job_id="j1",
        contract_id="c1",
        status=JobStatus.SUCCEEDED,
        result=_make_result(),
        created_at=now,
        finished_at=datetime(2026, 10, 22, 12, 3, 0),
    )
    jobs._persist(info)

    payload = captured[0]
    assert "created_at" in payload, "created_at must be sent to upsert_job"
    assert "finished_at" in payload, "finished_at must be sent to upsert_job"
    assert payload["created_at"] == now
    assert payload["finished_at"] == datetime(2026, 10, 22, 12, 3, 0)


def test_persist_payload_finished_at_none_for_running(monkeypatch, clear_memory_jobs):
    captured: list[dict] = []
    monkeypatch.setattr(jobs, "upsert_job", captured.append)

    info = JobInfo(job_id="j2", contract_id="c1", status=JobStatus.RUNNING)
    jobs._persist(info)

    assert captured[0]["finished_at"] is None
    assert isinstance(captured[0]["created_at"], datetime)


# ---------------------------------------------------------------------------
# (b) list_jobs merges in-memory + DB with dedup
# ---------------------------------------------------------------------------


def test_list_jobs_merges_memory_and_db(monkeypatch, clear_memory_jobs):
    # In-memory copy of j1 (fresher) plus an unrelated in-memory job.
    in_mem = JobInfo(job_id="j1", contract_id="c1", owner="u", status=JobStatus.SUCCEEDED)
    other = JobInfo(job_id="j3", contract_id="c9", owner="u", status=JobStatus.SUCCEEDED)
    with jobs._jobs_lock:
        jobs._jobs.update({in_mem.job_id: in_mem, other.job_id: other})

    # DB has j1 (duplicate, must NOT appear twice) and j2 (memory-missing).
    monkeypatch.setattr(
        postgres, "list_jobs", lambda limit=200: [{"job_id": "j1"}, {"job_id": "j2"}]
    )
    monkeypatch.setattr(postgres, "get_job", lambda job_id: _pg_record("j2", owner="u"))

    result = jobs.list_jobs()
    ids = [j.job_id for j in result]
    assert sorted(ids) == ["j1", "j2", "j3"], f"expected merge, got {ids}"
    # The in-memory copy of j1 wins (fresher), not the DB reconstruction.
    assert result[ids.index("j1")].job_id == "j1"
    assert len(ids) == len(set(ids)), "dedup failed: duplicate job ids"


def test_list_jobs_no_postgres_is_in_memory_only(monkeypatch, clear_memory_jobs):
    in_mem = JobInfo(job_id="j1", contract_id="c1", owner="u", status=JobStatus.SUCCEEDED)
    with jobs._jobs_lock:
        jobs._jobs[in_mem.job_id] = in_mem

    def _boom(limit=200):
        raise RuntimeError("postgres down")

    monkeypatch.setattr(postgres, "list_jobs", _boom)

    result = jobs.list_jobs()
    assert [j.job_id for j in result] == ["j1"]
    # Owner filter still applied.
    assert jobs.list_jobs(owner="other") == []


# ---------------------------------------------------------------------------
# (c) _latest_job_for finds an evicted job via the DB path
# ---------------------------------------------------------------------------


def test_latest_job_for_finds_evicted_job_via_db(monkeypatch, clear_memory_jobs):
    from app.api import routes_contracts

    # In-memory has no job for this contract at all (evicted); the DB does.
    monkeypatch.setattr(jobs, "list_jobs", lambda owner=None: [])
    monkeypatch.setattr(
        postgres, "list_job_ids_for_contract", lambda cid, owner=None, limit=20: ["j_evicted"]
    )
    monkeypatch.setattr(
        postgres, "get_jobs_by_ids",
        lambda ids, owner=None: [_pg_record("j_evicted")] if "j_evicted" in ids else [],
    )
    # pg.get_job returns nothing -> the reconstructed JobInfo must come from
    # the batched record path inside _latest_job_for.
    monkeypatch.setattr(postgres, "get_job", lambda job_id: None)

    job = routes_contracts._latest_job_for("c1", owner=None)
    assert job is not None
    assert job.job_id == "j_evicted"
    assert job.result is not None


def test_latest_job_for_prefers_in_memory_and_is_owner_scoped(monkeypatch, clear_memory_jobs):
    from app.api import routes_contracts

    mine = JobInfo(
        job_id="j_mine", contract_id="c1", owner="ana", status=JobStatus.SUCCEEDED,
        result=_make_result("c1"),
    )
    monkeypatch.setattr(
        jobs, "list_jobs", lambda owner=None: [mine] if owner in (None, "ana") else []
    )
    monkeypatch.setattr(postgres, "list_job_ids_for_contract", lambda *a, **k: ["j_mine"])
    monkeypatch.setattr(postgres, "get_jobs_by_ids", lambda *a, **k: [])

    # Owner sees their own job.
    assert routes_contracts._latest_job_for("c1", owner="ana").job_id == "j_mine"
    # A different owner is RLS-scoped out -> nothing (404 upstream), not a leak.
    assert routes_contracts._latest_job_for("c1", owner="vie") is None


# ---------------------------------------------------------------------------
# (d) a runner that dies with a BaseException ends FAILED, not RUNNING
# ---------------------------------------------------------------------------


def test_runner_base_exception_transitions_to_failed(monkeypatch, clear_memory_jobs):
    monkeypatch.setattr(jobs, "upsert_job", lambda payload: True)
    job = jobs.create_job("c1")

    def _abort(info):
        raise SystemExit(1)

    jobs.run_in_background(_abort, job.job_id, "c1")

    deadline = time.time() + 5
    while time.time() < deadline:
        with jobs._jobs_lock:
            current = jobs._jobs.get(job.job_id)
        if current is not None and current.status in {JobStatus.SUCCEEDED, JobStatus.FAILED}:
            break
        time.sleep(0.02)

    with jobs._jobs_lock:
        current = jobs._jobs.get(job.job_id)
    assert current is not None
    assert current.status == JobStatus.FAILED, f"job stuck at {current.status}"
    assert current.error
    assert "SystemExit" in current.error


def test_runner_normal_exception_records_real_error(monkeypatch, clear_memory_jobs):
    monkeypatch.setattr(jobs, "upsert_job", lambda payload: True)
    job = jobs.create_job("c1")

    def _fail(info):
        raise ValueError("boom")

    jobs.run_in_background(_fail, job.job_id, "c1")

    deadline = time.time() + 5
    while time.time() < deadline:
        with jobs._jobs_lock:
            current = jobs._jobs.get(job.job_id)
        if current is not None and current.status in {JobStatus.SUCCEEDED, JobStatus.FAILED}:
            break
        time.sleep(0.02)

    with jobs._jobs_lock:
        current = jobs._jobs.get(job.job_id)
    assert current is not None
    assert current.status == JobStatus.FAILED
    assert "boom" in current.error


# ---------------------------------------------------------------------------
# (e) corrupt stored result -> warning + non-404 response
# ---------------------------------------------------------------------------


def test_get_job_corrupt_result_is_flagged_not_dropped(monkeypatch, clear_memory_jobs):
    monkeypatch.setattr(
        postgres, "get_job", lambda job_id: _pg_record("j_bad", status="succeeded", result={"bogus": 1})
    )
    job = jobs.get_job("j_bad")
    assert job is not None
    assert job.status == JobStatus.SUCCEEDED
    assert job.result is None, "corrupt payload must not be returned as a result"
    assert job.result_error, "corruption must be recorded in result_error"


def test_contract_routes_corrupt_result_is_500_not_404(monkeypatch, clear_memory_jobs):
    from app.api import routes_contracts
    from app.main import app

    monkeypatch.setattr(routes_contracts, "_latest_job_for", lambda cid, owner=None: jobs.get_job("j_bad"))
    monkeypatch.setattr(
        postgres, "get_job", lambda job_id: _pg_record("j_bad", status="succeeded", result={"bogus": 1})
    )

    with TestClient(app) as client:
        r = client.get("/api/v1/contracts/c1/summary")
    assert r.status_code == 500, f"expected 500, got {r.status_code}: {r.text}"
    assert "unreadable" in r.text or "result" in r.text.lower()


# ---------------------------------------------------------------------------
# (f) FAILED job -> 409 with the error message
# ---------------------------------------------------------------------------


def test_contract_routes_failed_job_is_409_with_error(monkeypatch, clear_memory_jobs):
    from app.api import routes_contracts
    from app.main import app

    monkeypatch.setattr(
        routes_contracts,
        "_latest_job_for",
        lambda cid, owner=None: JobInfo(
            job_id="j_fail", contract_id="c1", status=JobStatus.FAILED, error="analysis blew up"
        ),
    )
    with TestClient(app) as client:
        r = client.get("/api/v1/contracts/c1/summary")
    assert r.status_code == 409, f"expected 409, got {r.status_code}"
    assert "analysis blew up" in r.text


def test_contract_routes_still_processing_is_409(monkeypatch, clear_memory_jobs):
    from app.api import routes_contracts
    from app.main import app

    monkeypatch.setattr(
        routes_contracts,
        "_latest_job_for",
        lambda cid, owner=None: JobInfo(job_id="j_run", contract_id="c1", status=JobStatus.RUNNING),
    )
    with TestClient(app) as client:
        r = client.get("/api/v1/contracts/c1/clauses")
    assert r.status_code == 409, f"expected 409, got {r.status_code}"
    assert "processing" in r.text


def test_contract_routes_unknown_contract_is_404(monkeypatch, clear_memory_jobs):
    from app.api import routes_contracts
    from app.main import app

    monkeypatch.setattr(routes_contracts, "_latest_job_for", lambda cid, owner=None: None)
    with TestClient(app) as client:
        r = client.get("/api/v1/contracts/c_missing/summary")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# (g) get_engine double-init under two threads
# ---------------------------------------------------------------------------


def test_get_engine_single_init_under_threads(monkeypatch):
    calls = {"n": 0}
    enter_gate = threading.Event()  # workers wait here until both have entered

    class _ProbeCtx:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, *a):
            return None

    class _FakeEngine:
        def connect(self):
            return _ProbeCtx()

    def _fake_create_engine(*a, **k):
        enter_gate.set()  # signal: both threads have entered get_engine
        enter_gate.wait(10)  # hold the first init so the second blocks on the lock
        calls["n"] += 1
        return _FakeEngine()

    class _FakeMeta:
        @staticmethod
        def create_all(engine):
            return None

    def _fake_get_settings():
        return type("S", (), {"database_url": "postgresql://x"})()

    monkeypatch.setattr(postgres, "create_engine", _fake_create_engine)
    monkeypatch.setattr(postgres, "get_settings", _fake_get_settings)
    monkeypatch.setattr(postgres.Base, "metadata", _FakeMeta())
    monkeypatch.setattr(postgres, "_ensure_owner_columns", lambda engine: None)

    results: list = []

    def _worker():
        results.append(postgres.get_engine())

    # Reset engine state for a clean double-init.
    postgres._engine = None
    postgres._AVAILABLE_CACHE.clear()
    postgres._AVAILABLE_CACHE["postgres"] = True

    t1 = threading.Thread(target=_worker)
    t2 = threading.Thread(target=_worker)
    t1.start()
    t2.start()
    # Both threads are inside get_engine (one holding the lock, one blocked on it).
    enter_gate.wait(10)
    enter_gate.set()  # release the held init
    t1.join(10)
    t2.join(10)

    assert calls["n"] == 1, f"create_engine called {calls['n']} times (expected exactly 1)"
    assert all(r is not None for r in results)


# ---------------------------------------------------------------------------
# (h) once-down re-probe after the bounded window
# ---------------------------------------------------------------------------


def test_unavailable_fast_fails_then_reprobes_after_window(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(postgres._time, "monotonic", lambda: now[0])

    # Simulate a down engine: mark unavailable (stamps unavailable_since=1000).
    postgres.set_postgres_unavailable()
    assert postgres._AVAILABLE_CACHE.get("unavailable_since") == 1000.0

    # Inside the window: fast-fail, no re-probe.
    assert postgres.postgres_available() is False
    now[0] = 1000.0 + postgres._PROBE_RETRY_SECONDS - 1
    assert postgres.postgres_available() is False

    # After the window: the flag resets so a re-probe is allowed.
    now[0] = 1000.0 + postgres._PROBE_RETRY_SECONDS
    assert postgres.postgres_available() is True, "bounded window must re-arm the probe"


def test_set_probe_window_extends_fastfail(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(postgres._time, "monotonic", lambda: now[0])
    postgres._AVAILABLE_CACHE.clear()
    postgres._AVAILABLE_CACHE["postgres"] = True

    # A freshly failed probe at t=1000 must fast-fail inside the window and
    # re-arm exactly at the window edge, regardless of any earlier timestamp.
    postgres.set_postgres_unavailable()
    assert postgres._AVAILABLE_CACHE.get("unavailable_since") == 1000.0
    assert postgres.postgres_available() is False
    now[0] = 1000.0 + postgres._PROBE_RETRY_SECONDS - 1
    assert postgres.postgres_available() is False
    now[0] = 1000.0 + postgres._PROBE_RETRY_SECONDS
    assert postgres.postgres_available() is True


# ---------------------------------------------------------------------------
# (i) bounded job worker pool (audit P2: one daemon thread per upload)
# ---------------------------------------------------------------------------


def _wait_for_terminal(job_ids: list[str], timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with jobs._jobs_lock:
            states = [
                jobs._jobs.get(jid)
                for jid in job_ids
            ]
        if all(j is not None and j.status in {JobStatus.SUCCEEDED, JobStatus.FAILED} for j in states):
            return
        time.sleep(0.02)
    raise AssertionError("jobs did not all reach a terminal state in time")


def test_job_pool_bounds_concurrency(monkeypatch, clear_memory_jobs):
    """More submissions than workers: at most N run concurrently and all
    jobs still complete (the pool queues the excess instead of threading)."""
    monkeypatch.setattr(jobs, "upsert_job", lambda payload: None)
    monkeypatch.setattr(jobs, "_job_workers", lambda: 2)  # pool of 2
    # Force a fresh pool sized 2 regardless of what the rest of the suite built.
    with jobs._executor_lock:
        jobs._executor = None

    n = 6
    delay = 0.15
    state = {"running": 0, "max": 0}
    state_lock = threading.Lock()
    done = threading.Event()
    done_count = 0

    def _slow(info: JobInfo):
        nonlocal done_count
        with state_lock:
            state["running"] += 1
            state["max"] = max(state["max"], state["running"])
        try:
            time.sleep(delay)
            return _make_result(info.contract_id)
        finally:
            with state_lock:
                state["running"] -= 1
                done_count += 1
                if done_count == n:
                    done.set()

    job_ids = []
    for i in range(n):
        job = jobs.create_job(f"c{i}")
        job_ids.append(job.job_id)
        jobs.run_in_background(_slow, job.job_id, f"c{i}")

    assert done.wait(15), "not all pool jobs finished"
    _wait_for_terminal(job_ids)

    # (b) at most N ran concurrently.
    assert state["max"] <= 2, f"concurrency peaked at {state['max']} (expected <= 2)"
    # (a) all jobs completed successfully.
    with jobs._jobs_lock:
        finished = [jobs._jobs[jid] for jid in job_ids]
    assert all(j.status == JobStatus.SUCCEEDED for j in finished)
    assert all(j.result is not None for j in finished)
