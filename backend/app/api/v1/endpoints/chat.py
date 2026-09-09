import json
import logging
from collections.abc import Iterable, Iterator
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from openai import RateLimitError

from app.agent.events import AgentEvent
from app.agent.runner import run_agent, stream_agent
from app.core.security import AuthenticatedUser, get_current_user
from app.schemas.chat import ChatMessageRequest, Citation
from app.schemas.confirmation import ConfirmationEvent
from app.services.conversation_service import TableConversationStore


logger = logging.getLogger(__name__)

router = APIRouter()

conversation_store = TableConversationStore()


def _sse_response(
    conversation_id: str,
    events: Iterable[AgentEvent],
    requested_by: str,
) -> Iterator[str]:
    # Keepalive comment to prevent proxy timeouts
    yield ": keepalive\n\n"

    start_data = json.dumps(
        {"conversationId": conversation_id},
        separators=(",", ":"),
    )
    yield f"event: start\ndata: {start_data}\n\n"

    assistant_chunks: list[str] = []
    citations: list[Citation] = []
    confirmation: ConfirmationEvent | None = None
    job_ids: list[str] = []

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

                citations.extend(event.citations)
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

                confirmation = event.confirmation
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

                # A replace confirmation already carries the staged path in
                # its own record; a delete confirmation never used one. Either
                # way, nothing is left to fall back to for the next turn.
                conversation_store.clear_pending_attachment(
                    conversation_id,
                    requested_by,
                )

            elif event.type == "job":
                if event.job is None:
                    raise ValueError(
                        "Job event is missing its payload"
                    )

                job_ids.append(event.job.job_id)
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

                # The staged attachment has just been handed to a job; it is
                # no longer "pending" for this conversation.
                conversation_store.clear_pending_attachment(
                    conversation_id,
                    requested_by,
                )

    except ValueError as exc:
        error_data = json.dumps(
            {"message": str(exc)},
            separators=(",", ":"),
        )
        yield f"event: error\ndata: {error_data}\n\n"
        yield "data: [DONE]\n\n"
        return

    except RateLimitError:
        # The chat deployment's quota is small enough that a few turns in a row
        # exhaust it. The SDK has already retried with backoff by this point,
        # so tell the user what actually happened instead of "request failed".
        logger.warning("Azure OpenAI rate limit reached while streaming")
        error_data = json.dumps(
            {
                "message": (
                    "The model is at capacity right now. "
                    "Wait a few seconds and send the message again."
                )
            },
            separators=(",", ":"),
        )
        yield f"event: error\ndata: {error_data}\n\n"
        yield "data: [DONE]\n\n"
        return

    except Exception:
        logger.exception("Agent stream failed")
        error_data = json.dumps(
            {"message": "Agent request failed"},
            separators=(",", ":"),
        )
        yield f"event: error\ndata: {error_data}\n\n"
        yield "data: [DONE]\n\n"
        return

    assistant_message = "".join(assistant_chunks)

    if assistant_message or citations or confirmation or job_ids:
        conversation_store.add_message(
            conversation_id=conversation_id,
            requested_by=requested_by,
            role="assistant",
            content=assistant_message,
            citations=citations,
            confirmation=confirmation,
            job_ids=job_ids,
        )

    done_data = json.dumps(
        {"conversationId": conversation_id},
        separators=(",", ":"),
    )
    yield f"event: done\ndata: {done_data}\n\n"
    yield "data: [DONE]\n\n"


@router.post("/message")
def send_message(
    request: ChatMessageRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    conversation_id = (
        request.conversation_id
        or f"conv_{uuid4().hex}"
    )
    try:
        history = conversation_store.get_messages(
            conversation_id,
            user.user_id,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail="Conversation access denied",
        ) from exc

    conversation_store.add_message(
        conversation_id=conversation_id,
        requested_by=user.user_id,
        role="user",
        content=request.message,
        attachments=request.attachments,
    )

    source_blob_path: str | None = None
    attachment_file_name: str | None = None
    fresh_attachment = len(request.attachments) == 1

    if fresh_attachment:
        source_blob_path = request.attachments[0].blob_path
        attachment_file_name = request.attachments[0].file_name
        conversation_store.set_pending_attachment(
            conversation_id=conversation_id,
            requested_by=user.user_id,
            blob_path=source_blob_path,
            file_name=attachment_file_name,
        )
    else:
        # The model may not have acted on an attachment in the turn it was
        # sent (a clarifying question first, say) - the client only sends the
        # file once, so later turns fall back to what was last staged here.
        pending = conversation_store.get_pending_attachment(
            conversation_id,
            user.user_id,
        )
        if pending:
            source_blob_path, attachment_file_name = pending

    if request.stream:
        return StreamingResponse(
            _sse_response(
                conversation_id,
                stream_agent(
                    request.message,
                    requested_by=user.user_id,
                    source_blob_path=source_blob_path,
                    attachment_file_name=attachment_file_name,
                    fresh_attachment=fresh_attachment,
                    history=history,
                ),
                user.user_id,
            ),
            media_type="text/event-stream",
        )

    try:
        answer = run_agent(
            request.message,
            history=history,
            source_blob_path=source_blob_path,
            attachment_file_name=attachment_file_name,
            fresh_attachment=fresh_attachment,
        )
        conversation_store.add_message(
            conversation_id=conversation_id,
            requested_by=user.user_id,
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
    conversationId: str | None = None,
    user: AuthenticatedUser = Depends(get_current_user),
):
    # The client asks for history before it holds a conversation id - a freshly
    # created thread, or a first load with nothing in localStorage. Requiring
    # the parameter made every one of those a 422, which is what the live SPA
    # was hitting on load. There is no per-user "most recent conversation"
    # lookup in the store, and silently resuming one would surprise a user who
    # deliberately started a new thread, so an id-less request is simply an
    # empty conversation.
    if conversationId is None:
        return {"conversationId": None, "messages": []}

    try:
        messages = conversation_store.get_messages(
            conversationId,
            user.user_id,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail="Conversation access denied",
        ) from exc

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
