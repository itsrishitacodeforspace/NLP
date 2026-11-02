"""Job status routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import Principal, get_current_principal
from app.services.jobs import get_job, list_jobs

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


def _owner_scope(principal: Principal) -> str | None:
    return principal.username if principal.authenticated else None


@router.get("/{job_id}")
def job_status(job_id: str, principal: Principal = Depends(get_current_principal)):
    job = get_job(job_id)
    owner = _owner_scope(principal)
    # Row-level security: another user's job is indistinguishable from a missing one.
    if not job or (owner is not None and job.owner != owner):
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("")
def list_all_jobs(principal: Principal = Depends(get_current_principal)):
    return {"jobs": list_jobs(owner=_owner_scope(principal))}
