from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_chat_message_calls_agent() -> None:
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
        "What is the rent?"
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
                "The monthly ",
                "rent is 5,000.",
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

    conversation_store._messages.clear()

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
        "conv_history_123"
    )

    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[0].content == "What is the rent?"
    assert messages[1].role == "assistant"
    assert messages[1].content == "The monthly rent is 5,000."


def test_chat_stream_saves_complete_assistant_message() -> None:
    from app.api.v1.endpoints.chat import conversation_store

    conversation_store._messages.clear()

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
                "The monthly ",
                "rent is 5,000.",
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
        "conv_stream_history_123"
    )

    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[0].content == "What is the rent?"
    assert messages[1].role == "assistant"
    assert messages[1].content == "The monthly rent is 5,000."


def test_get_chat_history_returns_saved_messages() -> None:
    from app.api.v1.endpoints.chat import conversation_store

    conversation_store._messages.clear()

    conversation_store.add_message(
        conversation_id="conv_history_get_123",
        role="user",
        content="What is the rent?",
    )

    conversation_store.add_message(
        conversation_id="conv_history_get_123",
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
