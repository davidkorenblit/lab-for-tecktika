from uuid import uuid4

from fastapi import APIRouter, HTTPException

from app.schemas.files import UploadUrlRequest, UploadUrlResponse
from app.services.upload_service import create_upload_url

from app.schemas.confirmation import (
    ConfirmActionRequest,
    ConfirmActionResponse,
)
from app.services.confirmation_service import confirmation_store
from app.services.job_manager import create_job_and_enqueue

router = APIRouter()


@router.post(
    "/upload-url",
    response_model=UploadUrlResponse,
)
def create_file_upload_url(
    request: UploadUrlRequest,
) -> UploadUrlResponse:
    try:
        result = create_upload_url(
            file_name=request.file_name,
            content_type=request.content_type,
            size=request.size,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    return UploadUrlResponse.model_validate(result)


@router.post(
    "/confirm-action",
    response_model=ConfirmActionResponse,
)
def confirm_action(
    request: ConfirmActionRequest,
) -> ConfirmActionResponse:
    """Validate and atomically claim a destructive action before queueing it.

    The Table ETag claim guarantees a single enqueue winner. There is an
    unavoidable cross-service failure window after the claim and before the job
    record/queue write because Azure Table Storage and Queue Storage do not share
    a transaction. A reconciliation/outbox mechanism would be needed to close it.
    """
    pending = confirmation_store.get(
        request.confirmation_id
    )

    if pending is None:
        raise HTTPException(
            status_code=404,
            detail="Confirmation not found",
        )

    if request.action.upper() != pending.action.value.lower().upper():
        raise HTTPException(
            status_code=400,
            detail="Confirmation action does not match",
        )

    if request.files != [pending.file_name]:
        raise HTTPException(
            status_code=400,
            detail="Confirmation file does not match",
        )

    if not request.confirmed:
        return ConfirmActionResponse(
            jobId=None,
            status="cancelled",
            message="Action cancelled",
        )

    if pending.completed:
        return ConfirmActionResponse(
            jobId=pending.job_id,
            status="queued",
            message="Action already confirmed",
        )

    reserved_job_id = str(uuid4())

    try:
        claimed, acquired = confirmation_store.claim(
            pending.confirmation_id,
            reserved_job_id,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail="Confirmation not found",
        ) from exc

    if not acquired:
        return ConfirmActionResponse(
            jobId=claimed.job_id,
            status="queued",
            message="Action already confirmed",
        )

    job = create_job_and_enqueue(
        operation=claimed.action,
        file_name=claimed.file_name,
        blob_name=claimed.blob_name,
        requested_by=claimed.requested_by,
        document_id=claimed.document_id,
        etag=claimed.etag,
        source_blob_path=claimed.source_blob_path,
        job_id=claimed.job_id,
    )

    return ConfirmActionResponse(
        jobId=job.RowKey,
        status="queued",
        message="Action confirmed and queued",
    )
