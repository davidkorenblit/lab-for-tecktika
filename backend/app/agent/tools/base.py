from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from openai.types.chat import ChatCompletionToolParam
from pydantic import BaseModel


ToolArgs = TypeVar("ToolArgs", bound=BaseModel)


class BaseTool(ABC, Generic[ToolArgs]):
    name: str
    description: str
    args_schema: type[ToolArgs]

    def validate_args(
        self,
        arguments: dict[str, object],
    ) -> ToolArgs:
        return self.args_schema.model_validate(arguments)

    @abstractmethod
    def execute(
        self,
        arguments: ToolArgs,
    ) -> object:
        raise NotImplementedError


def to_openai_tool(
    tool: BaseTool[BaseModel],
) -> ChatCompletionToolParam:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.args_schema.model_json_schema(),
        },
    }