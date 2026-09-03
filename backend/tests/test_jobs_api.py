from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_create_job_endpoint():
    with patch(
        "app.api.v1.endpoints.jobs.create_job_and_enqueue"
    ) as manager:
        manager.return_value.model_dump.return_value = {
            "PartitionKey": "JOB",
            "RowKey": "test-job-id",
            "operation": "ADD",
            "fileName": "contract.pdf",
            "status": "QUEUED",
            "requestedBy": "test-user",
        }

        response = client.post(
            "/api/v1/jobs",
            json={
                "operation": "ADD",
                "fileName": "contract.pdf",
                "blobName": "contract.pdf",
                "requestedBy": "test-user",
            },
        )

    assert response.status_code == 200
    assert response.json()["status"] == "QUEUED"

    manager.assert_called_once()
def test_get_job_endpoint():
    with patch(
        "app.api.v1.endpoints.jobs.get_job"
    ) as mock_get_job:
        mock_get_job.return_value = {
            "PartitionKey": "JOB",
            "RowKey": "123",
            "status": "RUNNING",
        }

        response = client.get(
            "/api/v1/jobs/123"
        )

    assert response.status_code == 200
    assert response.json()["RowKey"] == "123"
    assert response.json()["status"] == "RUNNING"

    mock_get_job.assert_called_once_with("123")    