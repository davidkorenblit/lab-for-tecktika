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
        "event_type": "CREATE",
        "blob_name": "sample.pdf",
        "document_id": "doc-123",
        "etag": "0x8D8"
    })
    msg = parse_queue_message(raw_json)
    assert msg.event_type == EventType.CREATE
    assert msg.blob_name == "sample.pdf"
    assert msg.document_id == "doc-123"
    assert msg.etag == "0x8D8"


def test_parse_queue_message_base64():
    """Verifies Base64 encoded queue messages are parsed correctly."""
    raw_json = json.dumps({
        "event_type": "DELETE",
        "blob_name": "sample.pdf",
        "document_id": "doc-123"
    })
    b64_encoded = base64.b64encode(raw_json.encode("utf-8")).decode("utf-8")
    
    msg = parse_queue_message(b64_encoded)
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
        event_type=EventType.CREATE,
        blob_name="file.pdf",
        document_id="doc-1"
    )
    dispatcher.dispatch(event)

    dispatcher.job_service.mark_running.assert_called_once_with("doc-1", "file.pdf")
    dispatcher.search_service.trigger_indexer.assert_called_once()
    dispatcher.job_service.mark_succeeded.assert_called_once_with("doc-1", "file.pdf")


@patch("services.dispatcher.SearchService")
@patch("services.dispatcher.BlobService")
@patch("services.dispatcher.JobService")
def test_dispatcher_idempotency_skip(MockJobService, MockBlobService, MockSearchService):
    """Verifies unchanged file (ETag match) skips indexer execution."""
    dispatcher = EventDispatcher()
    dispatcher.blob_service.is_file_changed.return_value = False

    event = QueueMessage(
        event_type=EventType.CREATE,
        blob_name="file.pdf",
        document_id="doc-1",
        etag="0xSAME"
    )
    dispatcher.dispatch(event)

    dispatcher.job_service.mark_running.assert_called_once_with("doc-1", "file.pdf")
    dispatcher.search_service.trigger_indexer.assert_not_called()
    dispatcher.job_service.mark_succeeded.assert_called_once_with("doc-1", "file.pdf")


@patch("services.dispatcher.SearchService")
@patch("services.dispatcher.BlobService")
@patch("services.dispatcher.JobService")
def test_dispatcher_delete_flow(MockJobService, MockBlobService, MockSearchService):
    """Verifies DELETE event triggers surgical deletion and updates status to SUCCEEDED."""
    dispatcher = EventDispatcher()

    event = QueueMessage(
        event_type=EventType.DELETE,
        blob_name="file.pdf",
        document_id="doc-1"
    )
    dispatcher.dispatch(event)

    dispatcher.job_service.mark_running.assert_called_once_with("doc-1", "file.pdf")
    dispatcher.search_service.delete_document_chunks.assert_called_once_with("doc-1")
    dispatcher.job_service.mark_succeeded.assert_called_once_with("doc-1", "file.pdf")


# --- 3. Tests for Error Handling & Table FAILED Status ---

@patch("function_app.dispatcher")
@patch("function_app.job_service")
def test_process_queue_message_failure_updates_table(mock_job_service, mock_dispatcher):
    """Verifies that execution failure updates Table Storage to FAILED and re-raises exception."""
    mock_dispatcher.dispatch.side_effect = Exception("Search Service Timeout")
    
    mock_msg = MagicMock()
    mock_msg.id = "msg-999"
    mock_msg.get_body.return_value = json.dumps({
        "event_type": "CREATE",
        "blob_name": "bad_file.pdf",
        "document_id": "doc-bad"
    }).encode("utf-8")

    with pytest.raises(Exception) as exc_info:
        process_queue_message(mock_msg)

    assert "Search Service Timeout" in str(exc_info.value)
    mock_job_service.mark_failed.assert_called_once_with(
        document_id="doc-bad",
        blob_name="bad_file.pdf",
        error_msg="Search Service Timeout"
    )
