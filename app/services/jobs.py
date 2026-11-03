"""Background job manager.

Jobs are stored in PostgreSQL; Neo4j persistence is invoked from inside the
worker function. We use FastAPI BackgroundTasks for the MVP (no Celery
required) but keep the abstraction so a Celery/Redis worker can replace it
later.
"""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Callable, Dict, Optional

from app.core.logging import get_logger
from app.core.time import utcnow
from app.db.postgres import upsert_job
from app.models.schemas import AnalysisResult, JobInfo, JobStatus
from app.utils.fs import unique_id

logger = get_logger()


# In-memory mirror of the job state for fast polling (DB is source of truth).
_jobs: Dict[str, JobInfo] = {}
_jobs_lock = threading.Lock()


MAX_IN_MEMORY_JOBS = 200


def _job_workers() -> int:
    """Worker count for the job pool, resolved lazily so tests can monkeypatch."""
    from app.core.config import get_settings

    try:
        return max(1, int(get_settings().job_worker_count))
    except Exception:  # pragma: no cover - config must never block a job
        return 4


# Bounded worker pool for background jobs. ``submit`` already queues when the
# pool is saturated (no new thread per upload — audit P2); the pool is a
# singleton and is never explicitly joined, mirroring the old daemon-thread
# semantics (queued work is dropped only if the process exits mid-flight).
_executor: Optional[ThreadPoolExecutor] = None
_executor_lock = threading.Lock()


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    with _executor_lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(
                max_workers=_job_workers(),
                thread_name_prefix="job",
            )
        return _executor


def create_job(contract_id: str, owner: str = "") -> JobInfo:
    job_id = unique_id("job")
    info = JobInfo(job_id=job_id, contract_id=contract_id, owner=owner, status=JobStatus.QUEUED)
    with _jobs_lock:
        if len(_jobs) >= MAX_IN_MEMORY_JOBS:
            finished = sorted(
                (j for j in _jobs.values() if j.status in {JobStatus.SUCCEEDED, JobStatus.FAILED}),
                key=lambda j: j.created_at,
            )
            for old in finished[: max(1, len(_jobs) - MAX_IN_MEMORY_JOBS + 1)]:
                _jobs.pop(old.job_id, None)
        _jobs[job_id] = info
    _persist(info)
    return info


def update_job(
    job_id: str,
    *,
    status: Optional[JobStatus] = None,
    progress: Optional[float] = None,
    message: Optional[str] = None,
    result: Optional[AnalysisResult] = None,
    error: Optional[str] = None,
) -> JobInfo:
    with _jobs_lock:
        info = _jobs.get(job_id)
        if info is None:
            raise KeyError(f"Unknown job: {job_id}")
        if status is not None:
            info.status = status
        if progress is not None:
            info.progress = progress
        if message is not None:
            info.message = message
        if result is not None:
            info.result = result
        if error is not None:
            info.error = error
        if status in {JobStatus.SUCCEEDED, JobStatus.FAILED}:
            info.finished_at = utcnow()
        _jobs[job_id] = info
    _persist(info)
    return info


def get_job(job_id: str) -> Optional[JobInfo]:
    with _jobs_lock:
        info = _jobs.get(job_id)
    if info:
        return info
    # Fallback to DB if in-memory state lost
    from app.db.postgres import get_job as pg_get_job

    record = pg_get_job(job_id)
    if not record:
        return None
    return _job_from_record(record)


def _job_from_record(record: dict) -> JobInfo:
    """Build a :class:`JobInfo` from a Postgres record.

    A stored result that fails to re-validate (schema drift / corruption) is
    kept as ``result=None`` with the failure recorded in ``result_error`` and
    a WARNING logged — a SUCCEEDED job must not silently look result-less.
    """
    job_id = record["job_id"]
    result = None
    result_error = None
    if record.get("result"):
        try:
            result = AnalysisResult.model_validate(record["result"])
        except Exception as exc:
            result = None
            result_error = f"Stored result could not be parsed: {exc}"
            logger.warning("Stored result for job {} failed validation: {}", job_id, exc)
    return JobInfo(
        job_id=job_id,
        contract_id=record["contract_id"] or "",
        owner=record.get("owner") or "",
        status=JobStatus(record["status"]) if record["status"] else JobStatus.QUEUED,
        progress=record["progress"] or 0.0,
        message=record["message"] or None,
        result=result,
        error=record["error"] or None,
        created_at=datetime.fromisoformat(record["created_at"]) if record["created_at"] else utcnow(),
        finished_at=datetime.fromisoformat(record["finished_at"]) if record["finished_at"] else None,
        result_error=result_error,
    )


def list_jobs(owner: Optional[str] = None) -> list[JobInfo]:
    """List jobs, optionally scoped to a single owner (row-level security).

    Merges the in-memory mirror with PostgreSQL so historical jobs survive a
    restart or the in-memory eviction cap. Deduplicated by ``job_id`` with the
    in-memory copy winning (it is fresher); the owner filter is applied to the
    merged list. When Postgres is unavailable this degrades to the in-memory
    mirror only (no-op fallback, never raises).
    """
    with _jobs_lock:
        memory_jobs = {j.job_id: j for j in _jobs.values()}
    try:
        from app.db.postgres import list_jobs as pg_list_jobs

        records = pg_list_jobs()
    except Exception as exc:  # pragma: no cover - defensive no-op
        logger.warning("Postgres job listing unavailable: {}", exc)
        records = []
    for record in records:
        job_id = record["job_id"]
        if job_id not in memory_jobs:
            job = get_job(job_id)
            if job is not None:
                memory_jobs[job_id] = job
    jobs = list(memory_jobs.values())
    if owner is not None:
        jobs = [j for j in jobs if j.owner == owner]
    jobs.sort(key=lambda j: j.created_at, reverse=True)
    return jobs


# ---------------------------------------------------------------------------
# Sync wrapper around an async worker
# ---------------------------------------------------------------------------


def run_in_background(
    func: Callable[[JobInfo], AnalysisResult],
    job_id: str,
    contract_id: str,
) -> None:
    """Run the synchronous worker on the bounded job pool.

    The pool (``JOB_WORKER_COUNT`` threads, default 4) bounds analysis
    concurrency; when it is saturated ``submit`` queues the runner instead of
    spawning a thread per upload (audit P2). The pool is never joined, which
    keeps the old daemon-thread semantics.
    """
    def _mark_failed(error: str, log: bool) -> None:
        """Force the job to a terminal FAILED state, in memory and in Postgres.

        Never raises: if the job was already evicted from the in-memory mirror
        the update simply does not happen (Postgres still records the
        transition when available).
        """
        try:
            update_job(
                job_id,
                status=JobStatus.FAILED,
                progress=1.0,
                message="Failed",
                error=error,
            )
        except KeyError:
            # Job evicted from memory; record the transition directly.
            with _jobs_lock:
                stuck = _jobs.get(job_id)
            if stuck is None or stuck.status in {JobStatus.SUCCEEDED, JobStatus.FAILED}:
                return
            stuck.status = JobStatus.FAILED
            stuck.progress = 1.0
            stuck.message = "Failed"
            stuck.error = error
            stuck.finished_at = utcnow()
            _persist(stuck)
        except Exception as persist_exc:  # pragma: no cover - defensive
            if log:
                logger.warning("Could not mark job {} failed: {}", job_id, persist_exc)

    def _runner():
        try:
            update_job(job_id, status=JobStatus.RUNNING, progress=0.05, message="Started")
        except KeyError:
            # Evicted before the runner even started: nothing left to update.
            return
        except Exception:
            return
        try:
            result = func(_jobs.get(job_id) or JobInfo(job_id=job_id, contract_id=contract_id))
            update_job(
                job_id,
                status=JobStatus.SUCCEEDED,
                progress=1.0,
                message="Completed",
                result=result,
            )
        except Exception as exc:
            if isinstance(exc, KeyError):
                # Job evicted from the in-memory mirror mid-run (the 200-cap
                # can remove it while the worker is still going): a normal
                # lifecycle race, not a failure.
                return
            logger.exception("Job {} failed", job_id)
            _mark_failed(str(exc), log=True)
        except BaseException as exc:
            # A BaseException (KeyboardInterrupt/SystemExit) or a C-level abort
            # must not leave the job RUNNING forever, in memory or in Postgres.
            logger.exception("Job {} aborted", job_id)
            _mark_failed(f"Aborted: {type(exc).__name__}", log=False)

    _get_executor().submit(_runner)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def _persist(info: JobInfo) -> None:
    payload = {
        "job_id": info.job_id,
        "contract_id": info.contract_id,
        "owner": info.owner,
        "status": info.status.value if isinstance(info.status, JobStatus) else str(info.status),
        "progress": info.progress,
        "message": info.message or "",
        "result": info.result.model_dump(mode="json") if info.result else {},
        "error": info.error or "",
        # Persist the job's own timestamps so Postgres ordering (created_at /
        # finished_at) reflects job lifetime, not upsert time.
        "created_at": info.created_at,
        "finished_at": info.finished_at,
    }
    try:
        upsert_job(payload)
    except Exception as exc:
        logger.warning("Job {} could not be persisted: {}", info.job_id, exc)
