from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.schemas.jobs import JobOperation
from app.services.blob_service import upload_document
from app.services.job_manager import create_job_and_enqueue

router = APIRouter()
MAX_FILE_SIZE = 50 * 1024 * 1024

@router.post("")
async def upload_document_endpoint(
    file: UploadFile = File(...),
):
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported",
        )

    document_id = str(uuid4())
    file_data = await file.read()

    MAX_FILE_SIZE = 50 * 1024 * 1024

    if len(file_data) > MAX_FILE_SIZE:
       raise HTTPException(
        status_code=413,
        detail="File size exceeds the 50 MB limit",
    )

    etag = upload_document(
        blob_name=file.filename,
        data=file_data,
        document_id=document_id,
    )

    job = create_job_and_enqueue(
        operation=JobOperation.ADD,
        file_name=file.filename,
        blob_name=file.filename,
        requested_by="local-dev",
        document_id=document_id,
        etag=etag,
    )

    return {
        "document_id": document_id,
        "file_name": file.filename,
        "etag": etag,
        "job_id": job.RowKey,
        "job_status": job.status,
    }