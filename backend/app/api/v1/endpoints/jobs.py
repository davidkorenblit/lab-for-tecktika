from fastapi import APIRouter, HTTPException

from app.schemas.jobs import CreateJobRequest
from app.services.job_manager import create_job_and_enqueue
from app.services.table_service import get_job


router = APIRouter()


@router.get("/health")
def jobs_health():
    return {
        "status": "ok",
        "service": "jobs",
    }


@router.post("")
def create_job(request: CreateJobRequest):
    job = create_job_and_enqueue(
        operation=request.operation,
        file_name=request.file_name,
        blob_name=request.blob_name,
        requested_by=request.requested_by,
    )

    return job.model_dump(
        by_alias=True,
        mode="json",
    )


@router.get("/{job_id}")
def read_job(job_id: str):
    job = get_job(job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Job not found",
        )

    return job