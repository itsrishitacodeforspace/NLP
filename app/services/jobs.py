"""Background job manager.

Jobs are stored in PostgreSQL; Neo4j persistence is invoked from inside the
worker function. We use FastAPI BackgroundTasks for the MVP (no Celery
required) but keep the abstraction so a Celery/Redis worker can replace it
later.
"""
from __future__ import annotations

import threading
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
    result = None
    if record.get("result"):
        try:
            result = AnalysisResult.model_validate(record["result"])
        except Exception:
            result = None
    return JobInfo(
        job_id=record["job_id"],
        contract_id=record["contract_id"] or "",
        owner=record.get("owner") or "",
        status=JobStatus(record["status"]) if record["status"] else JobStatus.QUEUED,
        progress=record["progress"] or 0.0,
        message=record["message"] or None,
        result=result,
        error=record["error"] or None,
        created_at=datetime.fromisoformat(record["created_at"]) if record["created_at"] else utcnow(),
        finished_at=datetime.fromisoformat(record["finished_at"]) if record["finished_at"] else None,
    )


def list_jobs(owner: Optional[str] = None) -> list[JobInfo]:
    """List jobs, optionally scoped to a single owner (row-level security)."""
    with _jobs_lock:
        jobs = list(_jobs.values())
    if not jobs:
        from app.db.postgres import list_jobs as pg_list_jobs

        jobs = [job for record in pg_list_jobs() if (job := get_job(record["job_id"])) is not None]
    if owner is not None:
        jobs = [j for j in jobs if j.owner == owner]
    return jobs


# ---------------------------------------------------------------------------
# Sync wrapper around an async worker
# ---------------------------------------------------------------------------


def run_in_background(
    func: Callable[[JobInfo], AnalysisResult],
    job_id: str,
    contract_id: str,
) -> None:
    """Run the synchronous worker in a daemon thread."""
    def _runner():
        info = update_job(job_id, status=JobStatus.RUNNING, progress=0.05, message="Started")
        try:
            result = func(info)
            update_job(
                job_id,
                status=JobStatus.SUCCEEDED,
                progress=1.0,
                message="Completed",
                result=result,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Job {} failed", job_id)
            update_job(
                job_id,
                status=JobStatus.FAILED,
                progress=1.0,
                message="Failed",
                error=str(exc),
            )

    t = threading.Thread(target=_runner, name=f"job-{job_id}", daemon=True)
    t.start()


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
    }
    try:
        upsert_job(payload)
    except Exception as exc:
        logger.warning("Job {} could not be persisted: {}", info.job_id, exc)
