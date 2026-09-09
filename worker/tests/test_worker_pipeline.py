import json
import base64
import pytest
from unittest.mock import MagicMock, patch

from models.queue_message import QueueMessage, EventType
from services.dispatcher import EventDispatcher
from function_app import parse_queue_message, process_queue_message


# --- 1. Tests for Queue Message Parsing ---

def test_parse_queue_message_json():
    """Verifies plain JSON queue messages are parsed correctly."""
    raw_json = json.dumps({
        "job_id": "job-100",
        "event_type": "CREATE",
        "blob_name": "sample.pdf",
        "document_id": "doc-123",
        "etag": "0x8D8"
    })
    msg = parse_queue_message(raw_json)
    assert msg.job_id == "job-100"
    assert msg.event_type == EventType.CREATE
    assert msg.blob_name == "sample.pdf"
    assert msg.document_id == "doc-123"
    assert msg.etag == "0x8D8"


def test_parse_queue_message_base64():
    """Verifies Base64 encoded queue messages are parsed correctly."""
    raw_json = json.dumps({
        "job_id": "job-101",
        "event_type": "DELETE",
        "blob_name": "sample.pdf",
        "document_id": "doc-123"
    })
    b64_encoded = base64.b64encode(raw_json.encode("utf-8")).decode("utf-8")
    
    msg = parse_queue_message(b64_encoded)
    assert msg.job_id == "job-101"
    assert msg.event_type == EventType.DELETE
    assert msg.blob_name == "sample.pdf"
    assert msg.document_id == "doc-123"


# --- 2. Tests for EventDispatcher Routing ---

@patch("services.dispatcher.SearchService")
@patch("services.dispatcher.BlobService")
@patch("services.dispatcher.JobService")
def test_dispatcher_create_flow(MockJobService, MockBlobService, MockSearchService):
    """Verifies CREATE event triggers indexer and updates status to RUNNING then SUCCEEDED."""
    dispatcher = EventDispatcher()
    dispatcher.blob_service.is_file_changed.return_value = True

    event = QueueMessage(
        job_id="job-1",
        event_type=EventType.CREATE,
        blob_name="file.pdf",
        document_id="doc-1"
    )
    dispatcher.dispatch(event)

    dispatcher.job_service.mark_running.assert_called_once_with("job-1", "doc-1", "file.pdf")
    dispatcher.search_service.wait_for_indexer.assert_called_once()
    dispatcher.job_service.mark_succeeded.assert_called_once_with("job-1", "doc-1", "file.pdf")


@patch("services.dispatcher.SearchService")
@patch("services.dispatcher.BlobService")
@patch("services.dispatcher.JobService")
def test_dispatcher_staging_copy_flow(MockJobService, MockBlobService, MockSearchService):
    """Verifies that if source_blob_path is present, copy_from_staging is triggered before indexing."""
    dispatcher = EventDispatcher()

    event = QueueMessage(
        job_id="job-staging",
        event_type=EventType.CREATE,
        blob_name="target.pdf",
        document_id="doc-staging",
        source_blob_path="staging/upload-123.pdf"
    )
    dispatcher.dispatch(event)

    dispatcher.blob_service.copy_from_staging.assert_called_once_with(
        source_blob_path="staging/upload-123.pdf",
        target_blob_name="target.pdf",
        document_id="doc-staging"
    )
    dispatcher.search_service.wait_for_indexer.assert_called_once()
    dispatcher.job_service.mark_succeeded.assert_called_once_with("job-staging", "doc-staging", "target.pdf")


@patch("services.dispatcher.SearchService")
@patch("services.dispatcher.BlobService")
@patch("services.dispatcher.JobService")
def test_dispatcher_terminal_job_idempotency_skip(MockJobService, MockBlobService, MockSearchService):
    """Verifies that a duplicate event for a SUCCEEDED job is skipped completely."""
    from models.job_entity import JobStatus
    dispatcher = EventDispatcher()
    dispatcher.job_service.get_job_status.return_value = JobStatus.SUCCEEDED

    event = QueueMessage(
        job_id="job-already-done",
        event_type=EventType.CREATE,
        blob_name="target.pdf",
        document_id="doc-staging",
        source_blob_path="staging/upload-123.pdf"
    )
    dispatcher.dispatch(event)

    dispatcher.job_service.mark_running.assert_not_called()
    dispatcher.blob_service.copy_from_staging.assert_not_called()
    dispatcher.search_service.wait_for_indexer.assert_not_called()


@patch("services.dispatcher.SearchService")
@patch("services.dispatcher.BlobService")
@patch("services.dispatcher.JobService")
def test_dispatcher_idempotency_skip(MockJobService, MockBlobService, MockSearchService):
    """Verifies unchanged file (ETag match on UPDATE) skips indexer execution."""
    dispatcher = EventDispatcher()
    dispatcher.blob_service.is_file_changed.return_value = False

    event = QueueMessage(
        job_id="job-2",
        event_type=EventType.UPDATE,
        blob_name="file.pdf",
        document_id="doc-1",
        etag="0xSAME"
    )
    dispatcher.dispatch(event)

    dispatcher.job_service.mark_running.assert_called_once_with("job-2", "doc-1", "file.pdf")
    dispatcher.search_service.wait_for_indexer.assert_not_called()
    dispatcher.job_service.mark_succeeded.assert_called_once_with("job-2", "doc-1", "file.pdf")


@patch("services.dispatcher.SearchService")
@patch("services.dispatcher.BlobService")
@patch("services.dispatcher.JobService")
def test_dispatcher_delete_flow(MockJobService, MockBlobService, MockSearchService):
    """Verifies DELETE event triggers surgical deletion and updates status to SUCCEEDED."""
    dispatcher = EventDispatcher()

    event = QueueMessage(
        job_id="job-3",
        event_type=EventType.DELETE,
        blob_name="file.pdf",
        document_id="doc-1"
    )
    dispatcher.dispatch(event)

    dispatcher.job_service.mark_running.assert_called_once_with("job-3", "doc-1", "file.pdf")
    dispatcher.search_service.delete_document_chunks.assert_called_once_with(
        "doc-1", file_name="file.pdf"
    )
    dispatcher.job_service.mark_succeeded.assert_called_once_with("job-3", "doc-1", "file.pdf")


# --- 3. Tests for Error Handling & Table FAILED Status ---

@patch("function_app.dispatcher")
@patch("function_app.job_service")
def test_process_queue_message_failure_updates_table(mock_job_service, mock_dispatcher):
    """Verifies that execution failure updates Table Storage to FAILED and re-raises exception."""
    mock_dispatcher.dispatch.side_effect = Exception("Search Service Timeout")
    
    mock_msg = MagicMock()
    mock_msg.id = "msg-999"
    mock_msg.get_body.return_value = json.dumps({
        "job_id": "job-bad",
        "event_type": "CREATE",
        "blob_name": "bad_file.pdf",
        "document_id": "doc-bad"
    }).encode("utf-8")

    with pytest.raises(Exception) as exc_info:
        process_queue_message(mock_msg)

    assert "Search Service Timeout" in str(exc_info.value)
    mock_job_service.mark_failed.assert_called_once_with(
        job_id="job-bad",
        document_id="doc-bad",
        blob_name="bad_file.pdf",
        error_msg="Search Service Timeout"
    )


@patch("services.dispatcher.SearchService")
@patch("services.dispatcher.BlobService")
@patch("services.dispatcher.JobService")
def test_staging_is_kept_until_indexing_succeeds(MockJobService, MockBlobService, MockSearchService):
    """
    A failure after the copy must leave the staging blob in place, otherwise the
    redelivery has nothing to copy and the message can only reach the poison
    queue. Observed live on 2026-09-09: BlobNotFound on every retry.
    """
    dispatcher = EventDispatcher()
    dispatcher.job_service.get_job_status.return_value = None
    dispatcher.search_service.wait_for_indexer.side_effect = RuntimeError("indexer failed")

    event = QueueMessage(
        job_id="job-retry",
        event_type=EventType.CREATE,
        blob_name="target.pdf",
        document_id="doc-retry",
        source_blob_path="f_1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d/target.pdf",
    )

    with pytest.raises(RuntimeError):
        dispatcher.dispatch(event)

    dispatcher.blob_service.copy_from_staging.assert_called_once()
    dispatcher.blob_service.delete_staging_blob.assert_not_called()


@patch("services.dispatcher.SearchService")
@patch("services.dispatcher.BlobService")
@patch("services.dispatcher.JobService")
def test_staging_is_cleaned_up_after_success(MockJobService, MockBlobService, MockSearchService):
    dispatcher = EventDispatcher()
    dispatcher.job_service.get_job_status.return_value = None

    event = QueueMessage(
        job_id="job-clean",
        event_type=EventType.CREATE,
        blob_name="target.pdf",
        document_id="doc-clean",
        source_blob_path="f_1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d/target.pdf",
    )
    dispatcher.dispatch(event)

    dispatcher.blob_service.delete_staging_blob.assert_called_once_with(
        "f_1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d/target.pdf"
    )


def test_indexer_status_is_read_from_the_sdk_enum():
    """
    str(IndexerExecutionStatus.IN_PROGRESS) is 'IndexerExecutionStatus.IN_PROGRESS',
    not 'inProgress'. Comparing the raw string meant a still-running indexer was
    reported as a failure - and a successful one would have been too.
    """
    from enum import Enum

    from services.search_service import SearchService

    class IndexerExecutionStatus(str, Enum):
        IN_PROGRESS = "inProgress"
        SUCCESS = "success"
        TRANSIENT_FAILURE = "transientFailure"

    normalize = SearchService._normalize_status

    assert normalize(IndexerExecutionStatus.IN_PROGRESS) == "inprogress"
    assert normalize(IndexerExecutionStatus.SUCCESS) == "success"
    assert normalize(IndexerExecutionStatus.TRANSIENT_FAILURE) == "transientfailure"
    assert normalize("inProgress") == "inprogress"
    assert normalize("success") == "success"


def test_job_status_is_persisted_as_its_value():
    """
    model_dump() hands the Tables SDK the enum member, which it stringifies to
    'JobStatus.FAILED'. The SPA polls for 'FAILED', and get_job_status() parses
    the same field back into the enum.
    """
    from models.job_entity import JobEntity, JobStatus

    entity = JobEntity(
        RowKey="job-1",
        document_id="doc-1",
        blob_name="a.pdf",
        status=JobStatus.FAILED,
    )

    dumped = entity.model_dump(mode="json", exclude_none=True)

    assert dumped["status"] == "FAILED"
    assert JobStatus(dumped["status"]) is JobStatus.FAILED
