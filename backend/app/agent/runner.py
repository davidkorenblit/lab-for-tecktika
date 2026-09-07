import json
from uuid import uuid4
from collections.abc import Iterator

from openai.types.chat import ChatCompletionMessage, ChatCompletionMessageParam
from pydantic import BaseModel

from app.agent.events import AgentEvent, JobEvent
from app.agent.prompts import SYSTEM_PROMPT
from app.agent.tools.base import BaseTool, to_openai_tool
from app.agent.tools.document_tools import (
    AddDocumentTool,
    DeleteDocumentTool,
    ReplaceDocumentTool,
)
from app.agent.tools.search_tool import SearchDocumentsTool
from app.schemas.chat import ChatHistoryMessage, Citation
from app.schemas.confirmation import ConfirmationEvent
from app.schemas.jobs import JobOperation
from app.services.azure_openai import (
    create_chat_completion,
    stream_chat_completion,
)
from app.services.confirmation_service import confirmation_store
from app.services.file_resolver import resolve_document
from app.services.job_manager import create_job_and_enqueue


TOOLS: tuple[BaseTool[BaseModel], ...] = (
    SearchDocumentsTool(),
    AddDocumentTool(),
    ReplaceDocumentTool(),
    DeleteDocumentTool(),
)

MAX_HISTORY_MESSAGES = 20
MAX_HISTORY_CHARACTERS = 24_000
AgentMessage = ChatCompletionMessageParam | ChatCompletionMessage


def _build_messages(
    user_message: str,
    history: list[ChatHistoryMessage] | None = None,
) -> list[AgentMessage]:
    messages: list[AgentMessage] = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]
    selected: list[ChatHistoryMessage] = []
    remaining_characters = MAX_HISTORY_CHARACTERS

    for message in reversed((history or [])[-MAX_HISTORY_MESSAGES:]):
        # History provides conversational context only. Tool arguments still go
        # through typed validation and destructive tools still require a fresh,
        # deterministic Blob Storage resolution and explicit confirmation.
        if message.role not in {"user", "assistant"}:
            continue
        if len(message.content) > remaining_characters:
            break
        selected.append(message)
        remaining_characters -= len(message.content)

    for message in reversed(selected):
        messages.append(
            {"role": message.role, "content": message.content}
        )

    messages.append({"role": "user", "content": user_message})
    return messages


def parse_tool_arguments(
    tool: BaseTool[BaseModel],
    raw_arguments: str,
) -> BaseModel:
    try:
        parsed = json.loads(raw_arguments)
    except json.JSONDecodeError as exc:
        raise ValueError("Tool arguments are not valid JSON") from exc

    if not isinstance(parsed, dict):
        raise ValueError("Tool arguments must be a JSON object")

    return tool.validate_args(parsed)


def get_tool_by_name(name: str) -> BaseTool[BaseModel]:
    for tool in TOOLS:
        if tool.name == name:
            return tool

    raise ValueError(f"Unknown tool: {name}")


def _prepare_confirmation(
    *,
    tool_name: str,
    arguments: BaseModel,
    requested_by: str,
    source_blob_path: str | None = None,
) -> ConfirmationEvent:
    file_name = getattr(arguments, "file_name", None)

    if not isinstance(file_name, str) or not file_name.strip():
        raise ValueError("A valid file name is required")

    matches = resolve_document(file_name)

    if not matches:
        raise ValueError(
            f"Document '{file_name}' was not found"
        )

    if len(matches) > 1:
        raise ValueError(
            f"Document name '{file_name}' is ambiguous"
        )

    resolved = matches[0]

    if tool_name == "delete_document":
        operation = JobOperation.DELETE
        summary = f"Delete '{resolved.file_name}'?"
        staged_path = None

    elif tool_name == "replace_document":
        if not source_blob_path:
            raise ValueError(
                "A staged attachment is required to replace a document"
            )

        operation = JobOperation.REPLACE
        summary = f"Replace '{resolved.file_name}'?"
        staged_path = source_blob_path

    else:
        raise ValueError(
            f"Tool '{tool_name}' does not use confirmation"
        )

    pending = confirmation_store.create(
        action=operation,
        file_name=resolved.file_name,
        blob_name=resolved.blob_name,
        document_id=resolved.document_id,
        requested_by=requested_by,
        source_blob_path=staged_path,
        etag=resolved.etag,
    )

    return ConfirmationEvent(
        confirmationId=pending.confirmation_id,
        action=operation.value.lower(),
        summary=summary,
        files=[resolved.file_name],
        destructive=True,
    )


def run_agent(
    user_message: str,
    *,
    history: list[ChatHistoryMessage] | None = None,
) -> str:
    messages = _build_messages(user_message, history)

    openai_tools = [to_openai_tool(tool) for tool in TOOLS]

    response = create_chat_completion(
        messages,
        tools=openai_tools,
    )

    assistant_message = response.choices[0].message
    tool_calls = assistant_message.tool_calls or []

    if not tool_calls:
        return assistant_message.content or ""

    messages.append(assistant_message)

    for tool_call in tool_calls:
        tool = get_tool_by_name(tool_call.function.name)

        if tool.name != "search_documents":
            raise ValueError(
                f"Tool '{tool.name}' requires streaming application-managed handling"
            )

        arguments = parse_tool_arguments(
            tool,
            tool_call.function.arguments,
        )

        result = tool.execute(arguments)

        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result, default=str),
            }
        )

    final_response = create_chat_completion(
        messages,
        tools=openai_tools,
    )

    return final_response.choices[0].message.content or ""


def stream_agent(
    user_message: str,
    *,
    requested_by: str,
    source_blob_path: str | None = None,
    history: list[ChatHistoryMessage] | None = None,
) -> Iterator[AgentEvent]:
    messages = _build_messages(user_message, history)

    openai_tools = [to_openai_tool(tool) for tool in TOOLS]

    response = create_chat_completion(
        messages,
        tools=openai_tools,
    )

    assistant_message = response.choices[0].message
    tool_calls = assistant_message.tool_calls or []

    if not tool_calls:
        content = assistant_message.content or ""

        if content:
            yield AgentEvent(
                type="delta",
                delta=content,
            )

        return

    messages.append(assistant_message)

    for tool_call in tool_calls:
        tool = get_tool_by_name(tool_call.function.name)

        arguments = parse_tool_arguments(
            tool,
            tool_call.function.arguments,
        )

        if tool.name in {
            "delete_document",
            "replace_document",
        }:
            confirmation = _prepare_confirmation(
                tool_name=tool.name,
                arguments=arguments,
                requested_by=requested_by,
                source_blob_path=source_blob_path,
            )

            yield AgentEvent(
                type="confirmation",
                confirmation=confirmation,
            )
            return

        if tool.name == "add_document":
            if not source_blob_path:
                raise ValueError(
                    "Adding a document requires an uploaded attachment"
                )

            file_name = getattr(arguments, "file_name", None)

            if not isinstance(file_name, str) or not file_name.strip():
                raise ValueError("A valid file name is required")

            existing_documents = resolve_document(file_name)

            if existing_documents:
                raise ValueError(
                    f"Document '{file_name}' already exists. "
                    "Replacing an existing document requires explicit confirmation."
                )

            job = create_job_and_enqueue(
                operation=JobOperation.ADD,
                file_name=file_name,
                blob_name=file_name,
                requested_by=requested_by,
                document_id=str(uuid4()),
                source_blob_path=source_blob_path,
            )

            yield AgentEvent(
                type="job",
                job=JobEvent(
                    jobId=job.RowKey,
                    status="queued",
                    fileName=file_name,
                ),
            )
            return

        result = tool.execute(arguments)

        if tool.name == "search_documents":
            citations: list[Citation] = []

            if isinstance(result, list):
                for item in result:
                    if not isinstance(item, dict):
                        continue

                    chunk_id = item.get("chunk_id")
                    file_name = item.get("file_name")

                    if not chunk_id or not file_name:
                        continue

                    score = item.get("reranker_score")
                    if score is None:
                        score = item.get("score")

                    citations.append(
                        Citation(
                            id=str(chunk_id),
                            fileName=str(file_name),
                            title=str(file_name),
                            url=(
                                str(item["source_url"])
                                if item.get("source_url")
                                else None
                            ),
                            page=(
                                int(item["page"])
                                if item.get("page") is not None
                                else None
                            ),
                            snippet=(
                                str(item["content"])
                                if item.get("content")
                                else None
                            ),
                            score=(
                                float(score)
                                if score is not None
                                else None
                            ),
                        )
                    )

            if citations:
                yield AgentEvent(
                    type="citations",
                    citations=citations,
                )

        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result, default=str),
            }
        )

    for chunk in stream_chat_completion(
        messages,
        tools=openai_tools,
    ):
        yield AgentEvent(
            type="delta",
            delta=chunk,
        )
