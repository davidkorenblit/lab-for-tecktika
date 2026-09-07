from uuid import uuid4

from azure.core.exceptions import ResourceNotFoundError

from app.azure_clients import get_table_service_client
from app.core.config import settings
from app.schemas.confirmation import PendingConfirmation
from app.schemas.jobs import JobOperation


CONFIRMATION_PARTITION_KEY = "pending-confirmations"


class TableConfirmationStore:
    def _get_table_client(self):
        service_client = get_table_service_client()

        return service_client.get_table_client(
            table_name=settings.job_status_table_name,
        )

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

        entity = {
            "PartitionKey": CONFIRMATION_PARTITION_KEY,
            "RowKey": confirmation.confirmation_id,
            **confirmation.model_dump(
                by_alias=True,
                mode="json",
            ),
        }

        self._get_table_client().create_entity(entity=entity)

        return confirmation

    def get(
        self,
        confirmation_id: str,
    ) -> PendingConfirmation | None:
        try:
            entity = self._get_table_client().get_entity(
                partition_key=CONFIRMATION_PARTITION_KEY,
                row_key=confirmation_id,
            )
        except ResourceNotFoundError:
            return None

        data = dict(entity)
        data.pop("PartitionKey", None)
        data.pop("RowKey", None)
        data.pop("Timestamp", None)
        data.pop("etag", None)

        return PendingConfirmation.model_validate(data)

    def mark_completed(
        self,
        confirmation_id: str,
        job_id: str,
    ) -> PendingConfirmation:
        confirmation = self.get(confirmation_id)

        if confirmation is None:
            raise KeyError(confirmation_id)

        confirmation.completed = True
        confirmation.job_id = job_id

        entity = {
            "PartitionKey": CONFIRMATION_PARTITION_KEY,
            "RowKey": confirmation.confirmation_id,
            **confirmation.model_dump(
                by_alias=True,
                mode="json",
            ),
        }

        self._get_table_client().update_entity(
            entity=entity,
            mode="merge",
        )

        return confirmation


confirmation_store = TableConfirmationStore()
