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