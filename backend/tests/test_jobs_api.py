from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_get_job_endpoint():
    with patch(
        "app.api.v1.endpoints.jobs.get_job"
    ) as mock_get_job:
        mock_get_job.return_value = {
            "PartitionKey": "ingestion-jobs",
            "RowKey": "123",
            "document_id": "doc-123",
            "blob_name": "contract.pdf",
            "status": "RUNNING",
        }

        response = client.get(
            "/api/v1/jobs/123"
        )

    assert response.status_code == 200
    assert response.json()["RowKey"] == "123"
    assert response.json()["document_id"] == "doc-123"
    assert response.json()["status"] == "RUNNING"

    mock_get_job.assert_called_once_with("123")


def test_get_job_not_found():
    with patch(
        "app.api.v1.endpoints.jobs.get_job"
    ) as mock_get_job:
        mock_get_job.return_value = None

        response = client.get(
            "/api/v1/jobs/999"
        )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Job not found"
    }

    mock_get_job.assert_called_once_with("999")


def test_get_job_status_endpoint():
    with patch(
        "app.api.v1.endpoints.jobs.get_job"
    ) as mock_get_job:
        mock_get_job.return_value = {
            "PartitionKey": "ingestion-jobs",
            "RowKey": "job-abc",
            "document_id": "doc-abc",
            "blob_name": "contract.pdf",
            "status": "SUCCEEDED",
            "etag": '"etag-abc"',
            "error_message": None,
        }

        # Test with /api/v1 prefix
        response = client.get(
            "/api/v1/jobs/job-abc/status"
        )
        assert response.status_code == 200
        body = response.json()
        assert body["job_id"] == "job-abc"
        assert body["status"] == "SUCCEEDED"
        assert body["document_id"] == "doc-abc"
        assert body["blob_name"] == "contract.pdf"

        # Test with /api prefix alias
        response_alias = client.get(
            "/api/jobs/job-abc/status"
        )
        assert response_alias.status_code == 200
        assert response_alias.json()["job_id"] == "job-abc"