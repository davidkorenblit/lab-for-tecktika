from fastapi import APIRouter, HTTPException

from app.services.table_service import get_job


router = APIRouter()


@router.get("/health")
def jobs_health():
    return {
        "status": "ok",
        "service": "jobs",
    }



@router.get("/{job_id}")
def read_job(job_id: str):
    job = get_job(job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Job not found",
        )

    return job


@router.get("/{job_id}/status")
def read_job_status(job_id: str):
    job = get_job(job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Job not found",
        )

    return {
        "job_id": job.get("RowKey", job_id),
        "status": job.get("status"),
        "document_id": job.get("document_id"),
        "blob_name": job.get("blob_name"),
        "etag": job.get("etag"),
        "error_message": job.get("error_message"),
    }