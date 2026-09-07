from collections.abc import Mapping
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import AuthenticatedUser, get_current_user
from app.services.table_service import get_job


router = APIRouter()


@router.get("/health")
def jobs_health():
    return {
        "status": "ok",
        "service": "jobs",
    }



def _get_owned_job(job_id: str, user_id: str) -> Mapping[str, Any]:
    job = get_job(job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Job not found",
        )

    if job.get("requested_by") != user_id:
        raise HTTPException(
            status_code=403,
            detail="Job access denied",
        )

    return job


@router.get("/{job_id}")
def read_job(
    job_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
):
    return _get_owned_job(job_id, user.user_id)


@router.get("/{job_id}/status")
def read_job_status(
    job_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
):
    job = _get_owned_job(job_id, user.user_id)

    return {
        "job_id": job.get("RowKey", job_id),
        "status": job.get("status"),
        "document_id": job.get("document_id"),
        "blob_name": job.get("blob_name"),
        "etag": job.get("etag"),
        "error_message": job.get("error_message"),
    }
