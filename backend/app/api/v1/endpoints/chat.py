import json
from collections.abc import Iterable, Iterator
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.agent.events import AgentEvent
from app.agent.runner import run_agent, stream_agent
from app.schemas.chat import ChatMessageRequest
from app.services.conversation_service import InMemoryConversationStore


router = APIRouter()

conversation_store = InMemoryConversationStore()


def _sse_response(
    conversation_id: str,
    events: Iterable[AgentEvent],
) -> Iterator[str]:
    start_data = json.dumps(
        {"conversationId": conversation_id},
        separators=(",", ":"),
    )
    yield f"event: start\ndata: {start_data}\n\n"

    assistant_chunks: list[str] = []

    try:
        for event in events:
            if event.type == "delta":
                chunk = event.delta or ""

                if not chunk:
                    continue

                assistant_chunks.append(chunk)

                delta_data = json.dumps(
                    {"delta": chunk},
                    separators=(",", ":"),
                )
                yield f"event: delta\ndata: {delta_data}\n\n"

            elif event.type == "citations":
                if event.citations is None:
                    raise ValueError(
                        "Citations event is missing its payload"
                    )

                citations_data = json.dumps(
                    [
                        citation.model_dump(
                            by_alias=True,
                            mode="json",
                            exclude_none=True,
                        )
                        for citation in event.citations
                    ],
                    separators=(",", ":"),
                )

                yield (
                    "event: citations\n"
                    f"data: {citations_data}\n\n"
                )

            elif event.type == "confirmation":
                if event.confirmation is None:
                    raise ValueError(
                        "Confirmation event is missing its payload"
                    )

                confirmation_data = json.dumps(
                    event.confirmation.model_dump(
                        by_alias=True,
                        mode="json",
                    ),
                    separators=(",", ":"),
                )

                yield (
                    "event: confirmation\n"
                    f"data: {confirmation_data}\n\n"
                )

            elif event.type == "job":
                if event.job is None:
                    raise ValueError(
                        "Job event is missing its payload"
                    )

                job_data = json.dumps(
                    event.job.model_dump(
                        by_alias=True,
                        mode="json",
                    ),
                    separators=(",", ":"),
                )

                yield (
                    "event: job\n"
                    f"data: {job_data}\n\n"
                )

    except ValueError as exc:
        error_data = json.dumps(
            {"message": str(exc)},
            separators=(",", ":"),
        )
        yield f"event: error\ndata: {error_data}\n\n"
        yield "data: [DONE]\n\n"
        return

    except Exception:
        error_data = json.dumps(
            {"message": "Agent request failed"},
            separators=(",", ":"),
        )
        yield f"event: error\ndata: {error_data}\n\n"
        yield "data: [DONE]\n\n"
        return

    assistant_message = "".join(assistant_chunks)

    if assistant_message:
        conversation_store.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=assistant_message,
        )

    yield "data: [DONE]\n\n"


@router.post("/message")
def send_message(request: ChatMessageRequest):
    conversation_id = (
        request.conversation_id
        or f"conv_{uuid4().hex}"
    )

    conversation_store.add_message(
        conversation_id=conversation_id,
        role="user",
        content=request.message,
    )

    source_blob_path: str | None = None

    if len(request.attachments) == 1:
        source_blob_path = request.attachments[0].blob_path

    if request.stream:
        return StreamingResponse(
            _sse_response(
                conversation_id,
                stream_agent(
                    request.message,
                    requested_by=conversation_id,
                    source_blob_path=source_blob_path,
                ),
            ),
            media_type="text/event-stream",
        )

    try:
        answer = run_agent(request.message)

        conversation_store.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=answer,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Agent request failed",
        ) from exc

    return {
        "conversationId": conversation_id,
        "message": answer,
    }


@router.get("/history")
def get_chat_history(
    conversationId: str,
):
    messages = conversation_store.get_messages(
        conversationId
    )

    return {
        "conversationId": conversationId,
        "messages": [
            message.model_dump(
                by_alias=True,
                mode="json",
            )
            for message in messages
        ],
    }
