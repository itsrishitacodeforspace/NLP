"""Background job manager.

Jobs are stored in PostgreSQL; Neo4j persistence is invoked from inside the
worker function. We use FastAPI BackgroundTasks for the MVP (no Celery
required) but keep the abstraction so a Celery/Redis worker can replace it
later.
"""
from __future__ import annotations

import asyncio
import threading
from datetime import datetime
from typing import Awaitable, Callable, Dict, Optional

from app.core.logging import get_logger
from app.db.postgres import upsert_job
from app.models.schemas import AnalysisResult, JobInfo, JobStatus
from app.utils.fs import unique_id


logger = get_logger()


# In-memory mirror of the job state for fast polling (DB is source of truth).
_jobs: Dict[str, JobInfo] = {}
_jobs_lock = threading.Lock()


def create_job(contract_id: str) -> JobInfo:
    job_id = unique_id("job")
    info = JobInfo(job_id=job_id, contract_id=contract_id, status=JobStatus.QUEUED)
    with _jobs_lock:
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
            info = JobInfo(job_id=job_id, contract_id="")
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
            info.finished_at = datetime.utcnow()
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
    return JobInfo(
        job_id=record["job_id"],
        contract_id=record["contract_id"] or "",
        status=JobStatus(record["status"]) if record["status"] else JobStatus.QUEUED,
        progress=record["progress"] or 0.0,
        message=record["message"] or "",
        error=record["error"] or None,
        created_at=datetime.fromisoformat(record["created_at"]) if record["created_at"] else datetime.utcnow(),
        finished_at=datetime.fromisoformat(record["finished_at"]) if record["finished_at"] else None,
    )


def list_jobs() -> list[JobInfo]:
    with _jobs_lock:
        return list(_jobs.values())


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
        "status": info.status.value if isinstance(info.status, JobStatus) else str(info.status),
        "progress": info.progress,
        "message": info.message or "",
        "result": info.result.model_dump() if info.result else {},
        "error": info.error or "",
    }
    upsert_job(payload)