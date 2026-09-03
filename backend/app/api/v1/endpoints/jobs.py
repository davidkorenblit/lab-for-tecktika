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