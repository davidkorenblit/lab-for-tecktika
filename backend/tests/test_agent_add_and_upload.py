from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.agent.events import AgentEvent
from app.agent.runner import stream_agent
from app.main import app
from app.core.config import settings


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
            patch(
                "app.agent.runner.resolve_document",
                return_value=[],
            ),
    ):
        events = list(
            stream_agent(
                "add this contract",
                requested_by="conv_123",
                source_blob_path="f_1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d/contract.pdf",
            )
        )

    assert len(events) == 1
    assert events[0].type == "job"
    assert events[0].job is not None
    assert events[0].job.job_id == "job_add_1"
    assert events[0].job.file_name == "contract.pdf"

    kwargs = create_job.call_args.kwargs
    assert kwargs["source_blob_path"] == "f_1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d/contract.pdf"
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
                        "blobPath": "f_1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d/contract.pdf",
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
            "blobPath": "f_1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d/contract.pdf",
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
    assert body["blobPath"] == "f_1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d/contract.pdf"
    assert body["uploadUrl"].startswith("https://")


def test_upload_url_rejects_unauthenticated_request() -> None:
    client = TestClient(app)

    with (
        patch.object(settings, "environment", "production"),
        patch.object(settings, "allow_local_auth_bypass", False),
    ):
        response = client.post(
            "/api/files/upload-url",
            json={
                "fileName": "contract.pdf",
                "contentType": "application/pdf",
                "size": 1024,
            },
        )

    assert response.status_code == 401


def test_job_status_route() -> None:
    client = TestClient(app)

    with patch(
        "app.api.v1.endpoints.jobs.get_job",
        return_value={
            "RowKey": "job_1",
            "status": "QUEUED",
            "requested_by": "local-dev",
        },
    ):
        response = client.get(
            "/api/v1/jobs/job_1/status"
        )

    assert response.status_code == 200
    assert response.json()["status"] == "QUEUED"


def test_chat_stream_emits_citations_event() -> None:
    client = TestClient(app)

    event = AgentEvent.model_validate(
        {
            "type": "citations",
            "citations": [
                {
                    "id": "chunk_1",
                    "fileName": "contract.pdf",
                    "title": "contract.pdf",
                    "url": "https://example.test/contract.pdf",
                    "page": 2,
                    "snippet": "Monthly rent: 5,000.",
                    "score": 3.75,
                }
            ],
        }
    )

    with patch(
        "app.api.v1.endpoints.chat.stream_agent",
        return_value=iter([event]),
    ):
        response = client.post(
            "/api/chat/message",
            json={
                "message": "What is the rent?",
                "conversationId": "conv_123",
                "stream": True,
            },
            headers={"Accept": "text/event-stream"},
        )

    assert response.status_code == 200
    assert "event: citations" in response.text
    assert '"fileName":"contract.pdf"' in response.text
    assert '"page":2' in response.text
    assert '"score":3.75' in response.text


def test_add_existing_document_does_not_create_job() -> None:
    first_response = MagicMock()
    tool_call = MagicMock()
    tool_call.id = "call_add_existing"
    tool_call.function.name = "add_document"
    tool_call.function.arguments = '{"file_name":"contract.pdf"}'
    first_response.choices[0].message.tool_calls = [tool_call]

    existing_document = MagicMock()

    with (
        patch(
            "app.agent.runner.create_chat_completion",
            return_value=first_response,
        ),
        patch(
            "app.agent.runner.resolve_document",
            return_value=[existing_document],
        ),
        patch(
            "app.agent.runner.create_job_and_enqueue",
        ) as create_job,
    ):
        try:
            list(
                stream_agent(
                    "add this contract",
                    requested_by="conv_123",
                    source_blob_path="f_1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d/contract.pdf",
                )
            )
        except ValueError as exc:
            assert "already exists" in str(exc)
            assert "explicit confirmation" in str(exc)
        else:
            raise AssertionError(
                "Existing document ADD should have been rejected"
            )

    create_job.assert_not_called()
