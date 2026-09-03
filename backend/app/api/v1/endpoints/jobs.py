from fastapi import APIRouter


router = APIRouter()


@router.get("/health")
def jobs_health():
    return {
        "status": "ok",
        "service": "jobs",
    }