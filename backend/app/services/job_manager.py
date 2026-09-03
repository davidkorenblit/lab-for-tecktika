from uuid import uuid4

from app.schemas.jobs import JobEntity, JobOperation, QueueMessage
from app.services.queue_service import send_job_message
from app.services.table_service import create_job


def create_job_and_enqueue(
    operation: JobOperation,
    file_name: str,
    blob_name: str,
    requested_by: str,
) -> JobEntity:
    job_id = uuid4()

    job = JobEntity(
        RowKey=job_id,
        operation=operation,
        fileName=file_name,
        requestedBy=requested_by,
    )

    message = QueueMessage(
        jobId=job_id,
        operation=operation,
        fileName=file_name,
        blobName=blob_name,
        requestedBy=requested_by,
        createdAt=job.created_at,
    )

    create_job(job)
    send_job_message(message)

    return job