from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.v1.endpoints.files import confirmation_store
from app.main import app
from app.schemas.jobs import JobEntity, JobOperation


client = TestClient(app)


def test_confirm_action_is_idempotent() -> None:
    confirmation_store._items.clear()

    pending = confirmation_store.create(
        action=JobOperation.DELETE,
        file_name="Q3-report.pdf",
        blob_name="Q3-report.pdf",
        document_id="doc_123",
        requested_by="user_123",
    )

    job = JobEntity(
        RowKey="job_7",
        document_id="doc_123",
        blob_name="Q3-report.pdf",
    )

    payload = {
        "confirmationId": pending.confirmation_id,
        "confirmed": True,
        "action": "delete",
        "files": ["Q3-report.pdf"],
    }

    with patch(
        "app.api.v1.endpoints.files.create_job_and_enqueue",
        return_value=job,
    ) as create_job:
        first = client.post(
            "/api/files/confirm-action",
            json=payload,
        )
        second = client.post(
            "/api/files/confirm-action",
            json=payload,
        )

    assert first.status_code == 200
    assert second.status_code == 200

    assert first.json()["jobId"] == "job_7"
    assert second.json()["jobId"] == "job_7"

    assert create_job.call_count == 1
