import logging
from collections.abc import Iterable, Iterator

from openai.types.chat import (
    ChatCompletion,
    ChatCompletionMessageParam,
    ChatCompletionToolParam,
)

from app.azure_clients import get_openai_client
from app.core.config import settings

logger = logging.getLogger(__name__)


def create_query_embedding(text: str) -> list[float]:
    if not text.strip():
        raise ValueError("text must not be empty")

    try:
        client = get_openai_client()

        response = client.embeddings.create(
            model=settings.openai_embedding_deployment,
            input=text,
            dimensions=1536,
        )

        if not response.data:
            raise RuntimeError("Azure OpenAI returned no embedding data")

        return response.data[0].embedding

    except Exception:
        logger.exception("Azure OpenAI embedding request failed")
        raise


def create_chat_completion(
    messages: Iterable[ChatCompletionMessageParam],
    *,
    tools: Iterable[ChatCompletionToolParam] | None = None,
) -> ChatCompletion:
    client = get_openai_client()

    kwargs = {
        "model": settings.openai_chat_deployment,
        "messages": messages,
    }

    if tools is not None:
        kwargs["tools"] = tools

    try:
        response = client.chat.completions.create(**kwargs)

        if not isinstance(response, ChatCompletion):
            raise RuntimeError(
                "Azure OpenAI returned an unexpected chat response type"
            )

        return response

    except Exception:
        logger.exception("Azure OpenAI chat completion request failed")
        raise


def stream_chat_completion(
    messages: Iterable[ChatCompletionMessageParam],
    *,
    tools: Iterable[ChatCompletionToolParam] | None = None,
) -> Iterator[str]:
    client = get_openai_client()

    kwargs = {
        "model": settings.openai_chat_deployment,
        "messages": messages,
        "stream": True,
    }

    if tools is not None:
        kwargs["tools"] = tools

    try:
        stream = client.chat.completions.create(**kwargs)

        for chunk in stream:
            if not chunk.choices:
                continue

            content = chunk.choices[0].delta.content

            if content:
                yield content

    except Exception:
        logger.exception("Azure OpenAI streaming request failed")
        raise
