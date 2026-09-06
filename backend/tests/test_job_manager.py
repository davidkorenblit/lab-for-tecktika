from unittest.mock import patch

from app.schemas.jobs import JobOperation
from app.services.job_manager import create_job_and_enqueue


def test_create_job_and_enqueue_includes_source_blob_path() -> None:
    with (
        patch("app.services.job_manager.create_job") as mock_create_job,
        patch("app.services.job_manager.send_job_message") as mock_send_job_message,
    ):
        create_job_and_enqueue(
            operation=JobOperation.ADD,
            file_name="contract.pdf",
            blob_name="contract.pdf",
            requested_by="test-user",
            document_id="doc-123",
            etag='"etag-123"',
            source_blob_path="staging/contract.pdf",
        )

    mock_create_job.assert_called_once()
    mock_send_job_message.assert_called_once()

    message = mock_send_job_message.call_args.args[0]

    assert message.blob_name == "contract.pdf"
    assert message.document_id == "doc-123"
    assert message.etag == '"etag-123"'
    assert message.source_blob_path == "staging/contract.pdf"
