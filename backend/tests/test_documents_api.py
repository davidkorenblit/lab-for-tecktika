from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_upload_rejects_file_larger_than_50mb():
    oversized_content = b"a" * (50 * 1024 * 1024 + 1)

    response = client.post(
        "/api/v1/documents",
        files={
            "file": (
                "large.pdf",
                oversized_content,
                "application/pdf",
            )
        },
    )

    assert response.status_code == 413
    assert response.json() == {
        "detail": "File size exceeds the 50 MB limit"
    }


def test_upload_document_success():
    with (
        patch(
            "app.api.v1.endpoints.documents.upload_document",
            return_value='"etag-123"',
        ) as mock_upload_document,
        patch(
            "app.api.v1.endpoints.documents.create_job_and_enqueue",
        ) as mock_create_job,
    ):
        mock_create_job.return_value.RowKey = "job-123"
        mock_create_job.return_value.status = "QUEUED"

        response = client.post(
            "/api/v1/documents",
            files={
                "file": (
                    "contract.pdf",
                    b"%PDF-1.4 test content",
                    "application/pdf",
                )
            },
        )

    assert response.status_code == 200

    body = response.json()

    assert body["file_name"] == "contract.pdf"
    assert body["etag"] == '"etag-123"'
    assert body["job_id"] == "job-123"
    assert body["job_status"] == "QUEUED"
    assert body["document_id"]

    mock_upload_document.assert_called_once()

    upload_call = mock_upload_document.call_args.kwargs
    assert upload_call["blob_name"] == "contract.pdf"
    assert upload_call["data"] == b"%PDF-1.4 test content"
    assert upload_call["document_id"] == body["document_id"]

    mock_create_job.assert_called_once()

    job_call = mock_create_job.call_args.kwargs
    assert job_call["blob_name"] == "contract.pdf"
    assert job_call["file_name"] == "contract.pdf"
    assert job_call["document_id"] == body["document_id"]
    assert job_call["etag"] == '"etag-123"'    