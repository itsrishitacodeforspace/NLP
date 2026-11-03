"""Contract upload + analysis routes."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from app.api.deps import Principal, get_current_principal, require_role
from app.core.config import get_settings
from app.core.exceptions import DocumentParseError, UnsupportedFormatError
from app.core.logging import get_logger
from app.core.time import utcnow
from app.db.postgres import upsert_contract_metadata
from app.db.queries import write_analysis
from app.models.schemas import (
    AnalysisResult,
    ContractType,
    JobInfo,
    JobStatus,
    PartySide,
)
from app.services.analyzer import analyse_bytes
from app.services.jobs import create_job, run_in_background

router = APIRouter(prefix="/api/v1/contracts", tags=["contracts"])
logger = get_logger()


_ALLOWED_EXT = {".pdf", ".docx", ".txt", ".md"}


def _ext_of(name: str) -> str:
    return "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""


@router.post("/upload", response_model=JobInfo)
async def upload_contract(
    file: UploadFile = File(...),
    contract_type: ContractType = Form(ContractType.OTHER),
    user_role: PartySide = Form(PartySide.CUSTOMER.value),
    jurisdiction: str = Form("India"),
    playbook_id: Optional[str] = Form(None),
    principal: Principal = Depends(require_role("admin", "analyst")),
):
    """Upload a contract and kick off background analysis.

    Requires an ``admin`` or ``analyst`` role when authentication is enabled.
    """
    settings = get_settings()
    filename = file.filename or "upload"
    ext = _ext_of(filename)
    if ext not in _ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    max_bytes = settings.max_upload_mb * 1024 * 1024
    if getattr(file, "size", None) is not None and file.size > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {settings.max_upload_mb} MB limit.",
        )
    contents = await file.read(max_bytes + 1)
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {settings.max_upload_mb} MB limit.",
        )
    if not contents.strip():
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    contract_id = _contract_id_for(filename, contents)
    owner = principal.username if principal.authenticated else ""
    job = await run_in_threadpool(create_job, contract_id, owner)

    def worker(info: JobInfo) -> AnalysisResult:
        def update_progress(p: float, msg: str) -> None:
            _update(info.job_id, progress=p, message=msg)
        update_progress(0.1, "Parsing document")
        try:
            result = analyse_bytes(
                contents,
                filename,
                contract_id=contract_id,
                contract_type=contract_type,
                user_role=user_role,
                jurisdiction=jurisdiction,
                enable_ocr=settings.enable_ocr_fallback,
            )
        except (DocumentParseError, UnsupportedFormatError) as exc:
            raise RuntimeError(str(exc)) from exc
        update_progress(0.7, "Persisting to graph")
        write_analysis(result)
        update_progress(0.85, "Saving metadata")
        upsert_contract_metadata(
            {
                "contract_id": contract_id,
                "title": result.contract.title,
                "file_name": result.contract.file_name,
                "contract_type": result.contract.contract_type.value,
                "owner": owner,
                "status": "succeeded",
                "overall_risk_score": result.contract.overall_risk_score,
                "overall_risk_level": result.contract.overall_risk_level.value,
                "payload": {"warnings": result.warnings, "obligation_count": len(result.obligations)},
            }
        )
        update_progress(1.0, "Done")
        return result

    run_in_background(worker, job.job_id, contract_id)
    return job


def _job_or_error(job: Optional[JobInfo], *, processing_detail: str) -> JobInfo:
    """Translate the job lookup result into the appropriate HTTP response.

    - no job at all -> 404 (truly unknown contract, or RLS-scoped out)
    - job in QUEUED/RUNNING -> 409 with the job status in the body
    - job FAILED -> 409 with the job's error message
    - job finished but its stored result is unreadable -> 500
    """
    if job is None:
        raise HTTPException(status_code=404, detail="Contract not found")
    if job.status in {JobStatus.QUEUED, JobStatus.RUNNING}:
        raise HTTPException(status_code=409, detail=processing_detail)
    if job.status == JobStatus.FAILED:
        raise HTTPException(
            status_code=409,
            detail=f"Analysis failed: {job.error or job.message or 'no error recorded'}",
        )
    if job.result is None:
        raise HTTPException(
            status_code=500,
            detail=job.result_error or "Stored result is missing or unreadable",
        )
    return job


@router.get("/{contract_id}/summary")
def contract_summary(contract_id: str, principal: Principal = Depends(get_current_principal)):
    job = _job_or_error(
        _latest_job_for(contract_id, owner=_owner_scope(principal)),
        processing_detail="Contract not found or still processing",
    )
    return job.result.contract


@router.get("/{contract_id}/clauses")
def contract_clauses(contract_id: str, principal: Principal = Depends(get_current_principal)):
    job = _job_or_error(
        _latest_job_for(contract_id, owner=_owner_scope(principal)),
        processing_detail="Contract still processing",
    )
    return {"clauses": job.result.clauses}


@router.get("/{contract_id}/obligations")
def contract_obligations(contract_id: str, principal: Principal = Depends(get_current_principal)):
    job = _job_or_error(
        _latest_job_for(contract_id, owner=_owner_scope(principal)),
        processing_detail="Contract still processing",
    )
    return {"obligations": job.result.obligations}


@router.get("/{contract_id}/risks")
def contract_risks(contract_id: str, principal: Principal = Depends(get_current_principal)):
    job = _job_or_error(
        _latest_job_for(contract_id, owner=_owner_scope(principal)),
        processing_detail="Contract still processing",
    )
    return {"risks": job.result.risks}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _update(job_id: str, *, progress: float, message: str) -> None:
    from app.services.jobs import update_job

    update_job(job_id, progress=progress, message=message)


def _contract_id_for(filename: str, contents: bytes) -> str:
    import hashlib

    digest = hashlib.sha256(contents).hexdigest()[:10]
    stamp = utcnow().strftime("%Y%m%d_%H%M%S")
    return f"c_{stamp}_{digest}"


def _owner_scope(principal: Principal) -> Optional[str]:
    """Owner filter for row-level security.

    Returns the caller's username when authenticated, or ``None`` (no filtering)
    when auth is disabled — so the open demo keeps seeing every contract.
    """
    return principal.username if principal.authenticated else None


def _candidate_key(job: JobInfo) -> tuple:
    """Sort key for picking the newest job: finished (or created) time desc,
    preferring succeeded jobs."""
    ts = job.finished_at or job.created_at
    return (ts, job.status == JobStatus.SUCCEEDED)


def _latest_job_for(contract_id: str, owner: Optional[str] = None) -> Optional[JobInfo]:
    """Return the newest job with a result for a contract.

    Queries PostgreSQL directly (``list_job_ids_for_contract`` + batched
    ``get_jobs_by_ids``) so evicted or post-restart jobs are found regardless
    of the in-memory mirror state; the in-memory cache is preferred for any
    job id it still holds (it is fresher). When Postgres is unavailable the
    in-memory mirror is used alone. When ``owner`` is given, only that owner's
    jobs are considered (row-level security).
    """
    from app.db.postgres import get_jobs_by_ids, list_job_ids_for_contract
    from app.services.jobs import _job_from_record, get_job, list_jobs

    # In-memory candidates (fresher than any DB copy).
    candidates = [j for j in list_jobs(owner=owner) if j.contract_id == contract_id]
    candidate_ids = {j.job_id for j in candidates}

    # DB candidates: fetch the ids for this contract, then batch the full rows.
    try:
        job_ids = list_job_ids_for_contract(contract_id, owner=owner)
    except Exception:
        job_ids = []
    if job_ids:
        try:
            records = get_jobs_by_ids(job_ids, owner=owner)
        except Exception:
            records = []
        by_id = {r.get("job_id"): r for r in records if r.get("job_id")}
        for job_id in job_ids:
            if job_id in candidate_ids or job_id not in by_id:
                continue
            job = get_job(job_id) or _job_from_record(by_id[job_id])
            if job is not None and job.contract_id == contract_id:
                candidates.append(job)
                candidate_ids.add(job_id)

    usable = [j for j in candidates if j.result is not None] or candidates
    if not usable:
        return None
    usable.sort(key=_candidate_key, reverse=True)
    return usable[0]
