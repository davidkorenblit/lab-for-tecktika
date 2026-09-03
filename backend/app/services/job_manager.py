from uuid import uuid4

from app.schemas.jobs import (
    EventType,
    JobEntity,
    JobOperation,
    QueueMessage,
)
from app.services.queue_service import send_job_message
from app.services.table_service import create_job


def map_operation_to_event_type(operation: JobOperation) -> EventType:
    mapping = {
        JobOperation.ADD: EventType.CREATE,
        JobOperation.REPLACE: EventType.UPDATE,
        JobOperation.DELETE: EventType.DELETE,
    }

    return mapping[operation]


def create_job_and_enqueue(
    operation: JobOperation,
    file_name: str,
    blob_name: str,
    requested_by: str,
    document_id: str,
    etag: str | None = None,
) -> JobEntity:
    job_id = str(uuid4())

    job = JobEntity(
        RowKey=job_id,
        document_id=document_id,
        blob_name=blob_name,
        etag=etag,
    )

    message = QueueMessage(
        job_id=job_id,
        event_type=map_operation_to_event_type(operation),
        blob_name=blob_name,
        document_id=document_id,
        etag=etag,
    )

    create_job(job)
    send_job_message(message)

    return job