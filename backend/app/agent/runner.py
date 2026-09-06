import json

from pydantic import BaseModel

from app.agent.tools.base import BaseTool
from app.agent.tools.document_tools import (
    AddDocumentTool,
    DeleteDocumentTool,
    ReplaceDocumentTool,
)
from app.agent.tools.search_tool import SearchDocumentsTool


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
