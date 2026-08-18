"""Job status routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.services.jobs import get_job, list_jobs


router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.get("/{job_id}")
def job_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("")
def list_all_jobs():
    return {"jobs": list_jobs()}