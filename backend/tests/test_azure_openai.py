from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import settings
from app.services.azure_openai import create_query_embedding


def test_create_query_embedding_returns_embedding() -> None:
    mock_client = MagicMock()
    mock_client.embeddings.create.return_value = SimpleNamespace(
        data=[
            SimpleNamespace(
                embedding=[0.1, 0.2, 0.3]
            )
        ]
    )

    with patch(
        "app.services.azure_openai.get_openai_client",
        return_value=mock_client,
    ):
        result = create_query_embedding("What is in the contract?")

    assert result == [0.1, 0.2, 0.3]

    mock_client.embeddings.create.assert_called_once_with(
        model=settings.openai_embedding_deployment,
        input="What is in the contract?",
        dimensions=1536,
    )


def test_create_query_embedding_rejects_empty_text() -> None:
    with pytest.raises(ValueError, match="text must not be empty"):
        create_query_embedding("   ")


def test_create_query_embedding_rejects_empty_response() -> None:
    mock_client = MagicMock()
    mock_client.embeddings.create.return_value = SimpleNamespace(
        data=[]
    )

    with patch(
        "app.services.azure_openai.get_openai_client",
        return_value=mock_client,
    ):
        with pytest.raises(
            RuntimeError,
            match="Azure OpenAI returned no embedding data",
        ):
            create_query_embedding("test")


def test_create_chat_completion_uses_chat_deployment() -> None:
    from openai.types.chat import ChatCompletion

    from app.services.azure_openai import create_chat_completion

    mock_client = MagicMock()

    mock_response = MagicMock(spec=ChatCompletion)
    mock_client.chat.completions.create.return_value = mock_response

    messages = [
        {
            "role": "user",
            "content": "What is in the contract?",
        }
    ]

    with patch(
        "app.services.azure_openai.get_openai_client",
        return_value=mock_client,
    ):
        result = create_chat_completion(messages)

    assert result is mock_response

    mock_client.chat.completions.create.assert_called_once_with(
        model=settings.openai_chat_deployment,
        messages=messages,
    )


def test_stream_chat_completion_yields_text_chunks() -> None:
    from app.services.azure_openai import stream_chat_completion

    mock_client = MagicMock()

    chunk_1 = SimpleNamespace(
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(content="Hello")
            )
        ]
    )

    chunk_2 = SimpleNamespace(
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(content=" world")
            )
        ]
    )

    mock_client.chat.completions.create.return_value = iter(
        [chunk_1, chunk_2]
    )

    messages = [
        {
            "role": "user",
            "content": "Hello",
        }
    ]

    with patch(
        "app.services.azure_openai.get_openai_client",
        return_value=mock_client,
    ):
        result = list(stream_chat_completion(messages))

    assert result == ["Hello", " world"]

    mock_client.chat.completions.create.assert_called_once_with(
        model=settings.openai_chat_deployment,
        messages=messages,
        stream=True,
    )


def test_create_chat_completion_passes_tools() -> None:
    from openai.types.chat import ChatCompletion

    from app.services.azure_openai import create_chat_completion

    mock_client = MagicMock()
    mock_response = MagicMock(spec=ChatCompletion)
    mock_client.chat.completions.create.return_value = mock_response

    messages = [
        {
            "role": "user",
            "content": "Delete contract.pdf",
        }
    ]

    tools = [
        {
            "type": "function",
            "function": {
                "name": "delete_document",
                "description": "Delete a document",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_name": {
                            "type": "string"
                        }
                    },
                    "required": ["file_name"],
                },
            },
        }
    ]

    with patch(
        "app.services.azure_openai.get_openai_client",
        return_value=mock_client,
    ):
        result = create_chat_completion(
            messages,
            tools=tools,
        )

    assert result is mock_response

    mock_client.chat.completions.create.assert_called_once_with(
        model=settings.openai_chat_deployment,
        messages=messages,
        tools=tools,
    )
