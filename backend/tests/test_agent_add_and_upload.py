from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.agent.events import AgentEvent
from app.agent.runner import stream_agent
from app.main import app


def test_add_document_creates_job_from_trusted_attachment() -> None:
    first_response = MagicMock()
    tool_call = MagicMock()
    tool_call.id = "call_add"
    tool_call.function.name = "add_document"
    tool_call.function.arguments = '{"file_name":"contract.pdf"}'
    first_response.choices[0].message.tool_calls = [tool_call]

    job = MagicMock()
    job.RowKey = "job_add_1"

    with (
        patch(
            "app.agent.runner.create_chat_completion",
            return_value=first_response,
        ),
        patch(
            "app.agent.runner.create_job_and_enqueue",
            return_value=job,
        ) as create_job,
    ):
        events = list(
            stream_agent(
                "add this contract",
                requested_by="conv_123",
                source_blob_path="f_1/contract.pdf",
            )
        )

    assert len(events) == 1
    assert events[0].type == "job"
    assert events[0].job is not None
    assert events[0].job.job_id == "job_add_1"
    assert events[0].job.file_name == "contract.pdf"

    kwargs = create_job.call_args.kwargs
    assert kwargs["source_blob_path"] == "f_1/contract.pdf"
    assert kwargs["file_name"] == "contract.pdf"


def test_chat_stream_emits_job_event() -> None:
    client = TestClient(app)

    event = AgentEvent.model_validate(
        {
            "type": "job",
            "job": {
                "jobId": "job_1",
                "status": "queued",
                "fileName": "contract.pdf",
            },
        }
    )

    with patch(
        "app.api.v1.endpoints.chat.stream_agent",
        return_value=iter([event]),
    ):
        response = client.post(
            "/api/v1/chat/message",
            json={
                "message": "add this",
                "conversationId": "conv_123",
                "stream": True,
                "attachments": [
                    {
                        "fileId": "f_1",
                        "fileName": "contract.pdf",
                        "size": 100,
                        "blobPath": "f_1/contract.pdf",
                    }
                ],
            },
            headers={"Accept": "text/event-stream"},
        )

    assert response.status_code == 200
    assert "event: job" in response.text
    assert '"jobId":"job_1"' in response.text


def test_upload_url_endpoint() -> None:
    client = TestClient(app)

    with patch(
        "app.api.v1.endpoints.files.create_upload_url",
        return_value={
            "uploadUrl": "https://storage.example/upload?sas=test",
            "fileId": "f_1",
            "blobPath": "f_1/contract.pdf",
            "expiresAt": "2026-09-07T02:00:00+00:00",
        },
    ):
        response = client.post(
            "/api/files/upload-url",
            json={
                "fileName": "contract.pdf",
                "contentType": "application/pdf",
                "size": 1024,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["fileId"] == "f_1"
    assert body["blobPath"] == "f_1/contract.pdf"
    assert body["uploadUrl"].startswith("https://")


def test_job_status_route() -> None:
    client = TestClient(app)

    with patch(
        "app.api.v1.endpoints.jobs.get_job",
        return_value={
            "RowKey": "job_1",
            "status": "QUEUED",
        },
    ):
        response = client.get(
            "/api/v1/jobs/job_1/status"
        )

    assert response.status_code == 200
    assert response.json()["status"] == "QUEUED"
