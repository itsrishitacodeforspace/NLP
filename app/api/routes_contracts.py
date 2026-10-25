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


@router.get("/{contract_id}/summary")
def contract_summary(contract_id: str, principal: Principal = Depends(get_current_principal)):
    job = _latest_job_for(contract_id, owner=_owner_scope(principal))
    if not job or not job.result:
        raise HTTPException(status_code=404, detail="Contract not found or still processing")
    return job.result.contract


@router.get("/{contract_id}/clauses")
def contract_clauses(contract_id: str, principal: Principal = Depends(get_current_principal)):
    job = _latest_job_for(contract_id, owner=_owner_scope(principal))
    if not job or not job.result:
        raise HTTPException(status_code=404, detail="Contract not found")
    return {"clauses": job.result.clauses}


@router.get("/{contract_id}/obligations")
def contract_obligations(contract_id: str, principal: Principal = Depends(get_current_principal)):
    job = _latest_job_for(contract_id, owner=_owner_scope(principal))
    if not job or not job.result:
        raise HTTPException(status_code=404, detail="Contract not found")
    return {"obligations": job.result.obligations}


@router.get("/{contract_id}/risks")
def contract_risks(contract_id: str, principal: Principal = Depends(get_current_principal)):
    job = _latest_job_for(contract_id, owner=_owner_scope(principal))
    if not job or not job.result:
        raise HTTPException(status_code=404, detail="Contract not found")
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


def _latest_job_for(contract_id: str, owner: Optional[str] = None) -> Optional[JobInfo]:
    """Return the newest completed job for a contract.

    Prefers the in-memory job cache, then falls back to PostgreSQL so results
    survive the in-memory eviction cap (``MAX_IN_MEMORY_JOBS``) or a restart.
    When ``owner`` is given, only that owner's jobs are considered.
    """
    from app.services.jobs import get_job, list_jobs

    candidates = [
        j for j in list_jobs(owner=owner) if j.contract_id == contract_id and j.result
    ]
    if candidates:
        candidates.sort(key=lambda j: j.created_at, reverse=True)
        return candidates[0]

    from app.db.postgres import list_job_ids_for_contract

    for job_id in list_job_ids_for_contract(contract_id, owner=owner):
        job = get_job(job_id)
        if job and job.result:
            return job
    return None
