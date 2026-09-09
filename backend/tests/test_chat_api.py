from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings


from app.agent.events import AgentEvent
client = TestClient(app)


def test_chat_message_calls_agent() -> None:
    from app.api.v1.endpoints.chat import conversation_store

    payload = {
        "message": "What is the rent?",
        "conversationId": "conv_123",
        "stream": False,
        "attachments": [],
    }

    with patch(
        "app.api.v1.endpoints.chat.run_agent",
        return_value="The monthly rent is 5,000.",
    ) as mock_run_agent:
        response = client.post(
            "/api/chat/message",
            json=payload,
        )

    assert response.status_code == 200
    assert response.json() == {
        "conversationId": "conv_123",
        "message": "The monthly rent is 5,000.",
    }

    mock_run_agent.assert_called_once_with(
        "What is the rent?",
        history=[],
        source_blob_path=None,
        attachment_file_name=None,
        fresh_attachment=False,
    )


def test_chat_message_streams_sse_response() -> None:
    payload = {
        "message": "What is the rent?",
        "conversationId": "conv_123",
        "stream": True,
        "attachments": [],
    }

    with patch(
        "app.api.v1.endpoints.chat.stream_agent",
        return_value=iter(
            [
                AgentEvent(type="delta", delta="The monthly "),
                AgentEvent(type="delta", delta="rent is 5,000."),
            ]
        ),
    ):
        response = client.post(
            "/api/chat/message",
            json=payload,
            headers={"Accept": "text/event-stream"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "text/event-stream"
    )

    body = response.text

    assert "event: start" in body
    assert '"conversationId":"conv_123"' in body
    assert "event: delta" in body
    assert '"delta":"The monthly "' in body
    assert '"delta":"rent is 5,000."' in body
    assert "data: [DONE]" in body


def test_chat_stream_creates_conversation_id_when_missing() -> None:
    payload = {
        "message": "Hello",
        "stream": True,
        "attachments": [],
    }

    with patch(
        "app.api.v1.endpoints.chat.stream_agent",
        return_value=iter(["Hello"]),
    ):
        response = client.post(
            "/api/chat/message",
            json=payload,
            headers={"Accept": "text/event-stream"},
        )

    assert response.status_code == 200

    body = response.text

    assert "event: start" in body
    assert '"conversationId":null' not in body
    assert '"conversationId":"' in body
    assert "data: [DONE]" in body


def test_chat_message_saves_conversation_history() -> None:
    from app.api.v1.endpoints.chat import conversation_store

    payload = {
        "message": "What is the rent?",
        "conversationId": "conv_history_123",
        "stream": False,
        "attachments": [],
    }

    with patch(
        "app.api.v1.endpoints.chat.run_agent",
        return_value="The monthly rent is 5,000.",
    ):
        response = client.post(
            "/api/chat/message",
            json=payload,
        )

    assert response.status_code == 200

    messages = conversation_store.get_messages(
        "conv_history_123", "local-dev"
    )

    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[0].content == "What is the rent?"
    assert messages[1].role == "assistant"
    assert messages[1].content == "The monthly rent is 5,000."


def test_chat_stream_saves_complete_assistant_message() -> None:
    from app.api.v1.endpoints.chat import conversation_store

    payload = {
        "message": "What is the rent?",
        "conversationId": "conv_stream_history_123",
        "stream": True,
        "attachments": [],
    }

    with patch(
        "app.api.v1.endpoints.chat.stream_agent",
        return_value=iter(
            [
                AgentEvent(type="delta", delta="The monthly "),
                AgentEvent(type="delta", delta="rent is 5,000."),
            ]
        ),
    ):
        response = client.post(
            "/api/chat/message",
            json=payload,
            headers={"Accept": "text/event-stream"},
        )

    assert response.status_code == 200

    messages = conversation_store.get_messages(
        "conv_stream_history_123", "local-dev"
    )

    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[0].content == "What is the rent?"
    assert messages[1].role == "assistant"
    assert messages[1].content == "The monthly rent is 5,000."


def test_get_chat_history_returns_saved_messages() -> None:
    from app.api.v1.endpoints.chat import conversation_store

    conversation_store.add_message(
        conversation_id="conv_history_get_123",
        requested_by="local-dev",
        role="user",
        content="What is the rent?",
    )

    conversation_store.add_message(
        conversation_id="conv_history_get_123",
        requested_by="local-dev",
        role="assistant",
        content="The monthly rent is 5,000.",
    )

    response = client.get(
        "/api/chat/history",
        params={
            "conversationId": "conv_history_get_123",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["conversationId"] == "conv_history_get_123"
    assert len(data["messages"]) == 2

    assert data["messages"][0]["role"] == "user"
    assert data["messages"][0]["content"] == "What is the rent?"

    assert data["messages"][1]["role"] == "assistant"
    assert (
        data["messages"][1]["content"]
        == "The monthly rent is 5,000."
    )


def test_chat_stream_emits_confirmation_event() -> None:
    from app.schemas.confirmation import ConfirmationEvent

    confirmation = ConfirmationEvent(
        confirmationId="cf_test_123",
        action="delete",
        summary="Delete 'Q3-report.pdf'?",
        files=["Q3-report.pdf"],
        destructive=True,
    )

    payload = {
        "message": "Delete Q3-report.pdf",
        "conversationId": "conv_delete_123",
        "stream": True,
        "attachments": [],
    }

    with patch(
        "app.api.v1.endpoints.chat.stream_agent",
        return_value=iter(
            [
                AgentEvent(
                    type="confirmation",
                    confirmation=confirmation,
                )
            ]
        ),
    ):
        response = client.post(
            "/api/chat/message",
            json=payload,
            headers={"Accept": "text/event-stream"},
        )

    assert response.status_code == 200

    body = response.text

    assert "event: confirmation" in body
    assert '"confirmationId":"cf_test_123"' in body
    assert '"action":"delete"' in body
    assert '"files":["Q3-report.pdf"]' in body
    assert '"destructive":true' in body
    assert "data: [DONE]" in body


def test_previous_turns_are_passed_to_stream_agent() -> None:
    from app.api.v1.endpoints.chat import conversation_store

    conversation_store.add_message(
        conversation_id="conv_context_123",
        requested_by="local-dev",
        role="user",
        content="Tell me about contract.pdf",
    )
    conversation_store.add_message(
        conversation_id="conv_context_123",
        requested_by="local-dev",
        role="assistant",
        content="It is the vendor agreement.",
    )

    with patch(
        "app.api.v1.endpoints.chat.stream_agent",
        return_value=iter([AgentEvent(type="delta", delta="30 days.")]),
    ) as mock_stream_agent:
        response = client.post(
            "/api/chat/message",
            json={
                "message": "What is its notice period?",
                "conversationId": "conv_context_123",
                "stream": True,
            },
        )

    assert response.status_code == 200
    history = mock_stream_agent.call_args.kwargs["history"]
    assert [message.content for message in history] == [
        "Tell me about contract.pdf",
        "It is the vendor agreement.",
    ]


def test_stream_history_preserves_message_metadata() -> None:
    from app.api.v1.endpoints.chat import conversation_store
    from app.agent.events import JobEvent
    from app.schemas.chat import Citation
    from app.schemas.confirmation import ConfirmationEvent

    attachment = {
        "fileId": "f_1",
        "fileName": "contract.pdf",
        "size": 100,
        "blobPath": "f_1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d/report.pdf",
    }
    citation = Citation(id="chunk_1", fileName="contract.pdf")
    confirmation = ConfirmationEvent(
        confirmationId="cf_1",
        action="replace",
        summary="Replace contract.pdf?",
        files=["contract.pdf"],
    )

    with patch(
        "app.api.v1.endpoints.chat.stream_agent",
        return_value=iter(
            [
                AgentEvent(type="citations", citations=[citation]),
                AgentEvent(type="confirmation", confirmation=confirmation),
                AgentEvent(
                    type="job",
                    job=JobEvent(
                        jobId="job_1",
                        status="queued",
                        fileName="contract.pdf",
                    ),
                ),
            ]
        ),
    ):
        response = client.post(
            "/api/chat/message",
            json={
                "message": "Replace it",
                "conversationId": "conv_metadata_123",
                "stream": True,
                "attachments": [attachment],
            },
        )

    assert response.status_code == 200
    history_response = client.get(
        "/api/chat/history",
        params={"conversationId": "conv_metadata_123"},
    ).json()
    user_message, assistant_message = history_response["messages"]
    assert user_message["attachments"] == [attachment]
    assert assistant_message["citations"][0]["id"] == "chunk_1"
    assert assistant_message["confirmation"]["confirmationId"] == "cf_1"
    assert assistant_message["jobIds"] == ["job_1"]


def test_get_chat_history_without_conversation_id_is_empty() -> None:
    # A fresh thread has no conversation id yet and the SPA still asks for
    # history on load; that must not be a validation error.
    response = client.get("/api/chat/history")

    assert response.status_code == 200

    data = response.json()

    assert data["conversationId"] is None
    assert data["messages"] == []


def test_chat_history_rejects_unauthenticated_request() -> None:
    with (
        patch.object(settings, "environment", "production"),
        patch.object(settings, "allow_local_auth_bypass", False),
    ):
        response = client.get(
            "/api/chat/history",
            params={"conversationId": "conv_private"},
        )

    assert response.status_code == 401


def test_attachment_survives_a_clarifying_question_and_completes_the_add() -> None:
    """
    Reproduces the reported bug: attach a file, the agent asks a clarifying
    question instead of acting immediately, the user's follow-up carries no
    attachment of its own - add_document must still see the staged file
    instead of failing with "Adding a document requires an uploaded
    attachment".
    """
    from app.agent.events import JobEvent

    attachment = {
        "fileId": "f_1",
        "fileName": "1125.pdf",
        "size": 100,
        "blobPath": "f_1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d/1125.pdf",
    }

    with patch(
        "app.api.v1.endpoints.chat.stream_agent",
        return_value=iter(
            [AgentEvent(type="delta", delta="Add it or replace an existing one?")]
        ),
    ) as first_call:
        first_response = client.post(
            "/api/chat/message",
            json={
                "message": "here is a document",
                "conversationId": "conv_pending_attachment",
                "stream": True,
                "attachments": [attachment],
            },
            headers={"Accept": "text/event-stream"},
        )

    assert first_response.status_code == 200
    assert first_call.call_args.kwargs["fresh_attachment"] is True
    assert (
        first_call.call_args.kwargs["source_blob_path"] == attachment["blobPath"]
    )

    with patch(
        "app.api.v1.endpoints.chat.stream_agent",
        return_value=iter(
            [
                AgentEvent(
                    type="job",
                    job=JobEvent(
                        jobId="job_pending_1",
                        status="queued",
                        fileName="1125.pdf",
                    ),
                )
            ]
        ),
    ) as second_call:
        second_response = client.post(
            "/api/chat/message",
            json={
                "message": "1125.pdf is the file name",
                "conversationId": "conv_pending_attachment",
                "stream": True,
                "attachments": [],
            },
            headers={"Accept": "text/event-stream"},
        )

    assert second_response.status_code == 200
    assert second_call.call_args.kwargs["fresh_attachment"] is False
    assert (
        second_call.call_args.kwargs["source_blob_path"] == attachment["blobPath"]
    )
    assert second_call.call_args.kwargs["attachment_file_name"] == "1125.pdf"

    # The job above consumed the staged attachment - nothing left to fall
    # back to on a later, unrelated turn.
    with patch(
        "app.api.v1.endpoints.chat.stream_agent",
        return_value=iter([AgentEvent(type="delta", delta="Anything else?")]),
    ) as third_call:
        client.post(
            "/api/chat/message",
            json={
                "message": "thanks",
                "conversationId": "conv_pending_attachment",
                "stream": True,
                "attachments": [],
            },
            headers={"Accept": "text/event-stream"},
        )

    assert third_call.call_args.kwargs["source_blob_path"] is None
    assert third_call.call_args.kwargs["attachment_file_name"] is None


def test_chat_history_rejects_another_user() -> None:
    from app.api.v1.endpoints.chat import conversation_store

    conversation_store.add_message(
        conversation_id="conv_private",
        requested_by="another-user",
        role="user",
        content="Private message",
    )

    response = client.get(
        "/api/chat/history",
        params={"conversationId": "conv_private"},
    )

    assert response.status_code == 403
