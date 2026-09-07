from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.confirmation import PendingConfirmation
from app.schemas.jobs import JobEntity, JobOperation


client = TestClient(app)


def test_confirm_action_is_idempotent() -> None:
    pending = PendingConfirmation(
        confirmationId="cf_123",
        action=JobOperation.DELETE,
        fileName="Q3-report.pdf",
        blobName="Q3-report.pdf",
        documentId="doc_123",
        requestedBy="user_123",
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

    def get_confirmation(
        confirmation_id: str,
    ) -> PendingConfirmation | None:
        assert confirmation_id == "cf_123"
        return pending

    def claim(
        confirmation_id: str,
        job_id: str,
    ) -> tuple[PendingConfirmation, bool]:
        assert confirmation_id == "cf_123"
        if pending.completed:
            return pending, False
        pending.completed = True
        pending.job_id = "job_7"
        return pending, True

    with (
        patch(
            "app.api.v1.endpoints.files.confirmation_store.get",
            side_effect=get_confirmation,
        ),
        patch(
            "app.api.v1.endpoints.files.confirmation_store.claim",
            side_effect=claim,
        ),
        patch(
            "app.api.v1.endpoints.files.create_job_and_enqueue",
            return_value=job,
        ) as create_job,
    ):
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
