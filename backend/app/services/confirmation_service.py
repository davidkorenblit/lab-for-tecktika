from uuid import uuid4

from app.schemas.confirmation import PendingConfirmation
from app.schemas.jobs import JobOperation


class InMemoryConfirmationStore:
    def __init__(self) -> None:
        self._items: dict[str, PendingConfirmation] = {}

    def create(
        self,
        *,
        action: JobOperation,
        file_name: str,
        blob_name: str,
        document_id: str,
        requested_by: str,
        source_blob_path: str | None = None,
        etag: str | None = None,
    ) -> PendingConfirmation:
        confirmation = PendingConfirmation(
            confirmationId=f"cf_{uuid4().hex}",
            action=action,
            fileName=file_name,
            blobName=blob_name,
            documentId=document_id,
            requestedBy=requested_by,
            sourceBlobPath=source_blob_path,
            etag=etag,
        )
        self._items[confirmation.confirmation_id] = confirmation
        return confirmation

    def get(
        self,
        confirmation_id: str,
    ) -> PendingConfirmation | None:
        return self._items.get(confirmation_id)

    def mark_completed(
        self,
        confirmation_id: str,
        job_id: str,
    ) -> PendingConfirmation:
        confirmation = self._items[confirmation_id]
        confirmation.completed = True
        confirmation.job_id = job_id
        return confirmation


confirmation_store = InMemoryConfirmationStore()
