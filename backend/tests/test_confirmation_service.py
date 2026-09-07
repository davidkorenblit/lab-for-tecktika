from unittest.mock import MagicMock, patch

from azure.core import MatchConditions
from azure.core.exceptions import ResourceModifiedError, ResourceNotFoundError
from azure.data.tables import TableEntity

from app.schemas.jobs import JobOperation
from app.services.confirmation_service import (
    CONFIRMATION_PARTITION_KEY,
    TableConfirmationStore,
)


def _mock_table():
    table_client = MagicMock()
    service_client = MagicMock()
    service_client.get_table_client.return_value = table_client
    return service_client, table_client


def _confirmation_entity(*, completed: bool = False) -> TableEntity:
    entity = TableEntity(
        {
            "PartitionKey": CONFIRMATION_PARTITION_KEY,
            "RowKey": "cf_123",
            "confirmationId": "cf_123",
            "action": "DELETE",
            "fileName": "contract.pdf",
            "blobName": "contract.pdf",
            "documentId": "doc_123",
            "requestedBy": "user_123",
            "sourceBlobPath": None,
            "etag": '"blob-etag-1"',
            "completed": completed,
            "jobId": "job_winner" if completed else None,
        }
    )
    entity.metadata["etag"] = 'W/"table-etag-1"'
    return entity


def test_create_confirmation_persists_to_table() -> None:
    service_client, table_client = _mock_table()

    with patch(
        "app.services.confirmation_service.get_table_service_client",
        return_value=service_client,
    ):
        confirmation = TableConfirmationStore().create(
            action=JobOperation.DELETE,
            file_name="contract.pdf",
            blob_name="contract.pdf",
            document_id="doc_123",
            requested_by="user_123",
            etag="etag_1",
        )

    entity = table_client.create_entity.call_args.kwargs["entity"]

    assert entity["PartitionKey"] == CONFIRMATION_PARTITION_KEY
    assert entity["RowKey"] == confirmation.confirmation_id
    assert entity["fileName"] == "contract.pdf"
    assert entity["documentId"] == "doc_123"
    assert entity["completed"] is False


def test_get_confirmation_reads_from_table() -> None:
    service_client, table_client = _mock_table()

    table_client.get_entity.return_value = {
        "PartitionKey": CONFIRMATION_PARTITION_KEY,
        "RowKey": "cf_123",
        "confirmationId": "cf_123",
        "action": "DELETE",
        "fileName": "contract.pdf",
        "blobName": "contract.pdf",
        "documentId": "doc_123",
        "requestedBy": "user_123",
        "sourceBlobPath": None,
        "completed": False,
        "jobId": None,
    }

    with patch(
        "app.services.confirmation_service.get_table_service_client",
        return_value=service_client,
    ):
        confirmation = TableConfirmationStore().get("cf_123")

    assert confirmation is not None
    assert confirmation.confirmation_id == "cf_123"
    assert confirmation.file_name == "contract.pdf"


def test_get_missing_confirmation_returns_none() -> None:
    service_client, table_client = _mock_table()

    table_client.get_entity.side_effect = ResourceNotFoundError(
        "not found"
    )

    with patch(
        "app.services.confirmation_service.get_table_service_client",
        return_value=service_client,
    ):
        confirmation = TableConfirmationStore().get("cf_missing")

    assert confirmation is None


def test_mark_completed_persists_job_id() -> None:
    service_client, table_client = _mock_table()

    table_client.get_entity.return_value = {
        "PartitionKey": CONFIRMATION_PARTITION_KEY,
        "RowKey": "cf_123",
        "confirmationId": "cf_123",
        "action": "DELETE",
        "fileName": "contract.pdf",
        "blobName": "contract.pdf",
        "documentId": "doc_123",
        "requestedBy": "user_123",
        "sourceBlobPath": None,
        "completed": False,
        "jobId": None,
    }

    with patch(
        "app.services.confirmation_service.get_table_service_client",
        return_value=service_client,
    ):
        confirmation = TableConfirmationStore().mark_completed(
            "cf_123",
            "job_7",
        )

    assert confirmation.completed is True
    assert confirmation.job_id == "job_7"

    entity = table_client.update_entity.call_args.kwargs["entity"]

    assert entity["completed"] is True
    assert entity["jobId"] == "job_7"


def test_claim_uses_table_etag_and_preserves_blob_etag() -> None:
    service_client, table_client = _mock_table()
    table_client.get_entity.return_value = _confirmation_entity()

    with patch(
        "app.services.confirmation_service.get_table_service_client",
        return_value=service_client,
    ):
        confirmation, acquired = TableConfirmationStore().claim(
            "cf_123", "job_7"
        )

    assert acquired is True
    assert confirmation.etag == '"blob-etag-1"'
    assert confirmation.job_id == "job_7"
    table_client.update_entity.assert_called_once()
    kwargs = table_client.update_entity.call_args.kwargs
    assert kwargs["etag"] == 'W/"table-etag-1"'
    assert kwargs["match_condition"] == MatchConditions.IfNotModified
    assert kwargs["entity"]["etag"] == '"blob-etag-1"'


def test_claim_etag_conflict_returns_concurrent_winner() -> None:
    service_client, table_client = _mock_table()
    table_client.get_entity.side_effect = [
        _confirmation_entity(),
        _confirmation_entity(completed=True),
    ]
    table_client.update_entity.side_effect = ResourceModifiedError(
        "condition not met"
    )

    with patch(
        "app.services.confirmation_service.get_table_service_client",
        return_value=service_client,
    ):
        confirmation, acquired = TableConfirmationStore().claim(
            "cf_123", "job_loser"
        )

    assert acquired is False
    assert confirmation.completed is True
    assert confirmation.job_id == "job_winner"
    assert confirmation.etag == '"blob-etag-1"'
