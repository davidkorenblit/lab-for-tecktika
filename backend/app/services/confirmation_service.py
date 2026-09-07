from uuid import uuid4

from azure.core import MatchConditions
from azure.core.exceptions import (
    ResourceModifiedError,
    ResourceNotFoundError,
)

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

    @staticmethod
    def _to_confirmation(entity) -> PendingConfirmation:
        data = dict(entity)

        data.pop("PartitionKey", None)
        data.pop("RowKey", None)
        data.pop("Timestamp", None)

        # Do NOT remove "etag" here.
        # This field is the Blob/document ETag stored by our application.
        # The Azure Table entity ETag lives separately in entity.metadata.
        return PendingConfirmation.model_validate(data)

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

        return self._to_confirmation(entity)

    def claim(
        self,
        confirmation_id: str,
        job_id: str,
    ) -> tuple[PendingConfirmation, bool]:
        """
        Atomically claim a confirmation.

        Returns:
            (confirmation, True)
                This request successfully claimed it.

            (confirmation, False)
                Another request already claimed/completed it.
        """
        table_client = self._get_table_client()

        try:
            entity = table_client.get_entity(
                partition_key=CONFIRMATION_PARTITION_KEY,
                row_key=confirmation_id,
            )
        except ResourceNotFoundError as exc:
            raise KeyError(confirmation_id) from exc

        confirmation = self._to_confirmation(entity)

        if confirmation.completed:
            return confirmation, False

        table_etag = entity.metadata.get("etag")

        if not table_etag:
            raise RuntimeError(
                "Azure Table entity did not contain an ETag"
            )

        claimed = confirmation.model_copy(
            update={
                "completed": True,
                "job_id": job_id,
            }
        )

        update_entity = {
            "PartitionKey": CONFIRMATION_PARTITION_KEY,
            "RowKey": claimed.confirmation_id,
            **claimed.model_dump(
                by_alias=True,
                mode="json",
            ),
        }

        try:
            table_client.update_entity(
                entity=update_entity,
                mode="merge",
                etag=table_etag,
                match_condition=MatchConditions.IfNotModified,
            )
        except ResourceModifiedError:
            # Another request changed the entity after our GET.
            latest = self.get(confirmation_id)

            if latest is None:
                raise KeyError(confirmation_id)

            return latest, False

        return claimed, True

    def mark_completed(
        self,
        confirmation_id: str,
        job_id: str,
    ) -> PendingConfirmation:
        """
        Kept for backwards compatibility with existing tests/callers.

        New confirmation execution should use claim().
        """
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
