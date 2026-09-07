import json
from uuid import uuid4
from collections.abc import Iterator

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


def run_agent(user_message: str) -> str:
    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": user_message,
        },
    ]

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
) -> Iterator[AgentEvent]:
    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": user_message,
        },
    ]

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
