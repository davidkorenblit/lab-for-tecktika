import json
from collections.abc import Iterable, Iterator
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.agent.runner import run_agent, stream_agent
from app.schemas.chat import ChatMessageRequest
from app.services.conversation_service import InMemoryConversationStore


router = APIRouter()

conversation_store = InMemoryConversationStore()


def _sse_response(
    conversation_id: str,
    chunks: Iterable[str],
) -> Iterator[str]:
    start_data = json.dumps(
        {"conversationId": conversation_id},
        separators=(",", ":"),
    )
    yield f"event: start\ndata: {start_data}\n\n"

    assistant_chunks: list[str] = []

    for chunk in chunks:
        assistant_chunks.append(chunk)

        delta_data = json.dumps(
            {"delta": chunk},
            separators=(",", ":"),
        )
        yield f"event: delta\ndata: {delta_data}\n\n"

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

    if request.stream:
        return StreamingResponse(
            _sse_response(
                conversation_id,
                stream_agent(request.message),
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