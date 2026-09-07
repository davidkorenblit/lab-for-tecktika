import json
from collections.abc import Iterator

from pydantic import BaseModel

from app.agent.prompts import SYSTEM_PROMPT
from app.agent.tools.base import BaseTool, to_openai_tool
from app.agent.tools.document_tools import (
    AddDocumentTool,
    DeleteDocumentTool,
    ReplaceDocumentTool,
)
from app.agent.tools.search_tool import SearchDocumentsTool
from app.services.azure_openai import (
    create_chat_completion,
    stream_chat_completion,
)


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
                f"Tool '{tool.name}' requires application-managed confirmation"
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


def stream_agent(user_message: str) -> Iterator[str]:
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
            yield content

        return

    messages.append(assistant_message)

    for tool_call in tool_calls:
        tool = get_tool_by_name(tool_call.function.name)

        if tool.name != "search_documents":
            raise ValueError(
                f"Tool '{tool.name}' requires application-managed confirmation"
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

    yield from stream_chat_completion(
        messages,
        tools=openai_tools,
    )