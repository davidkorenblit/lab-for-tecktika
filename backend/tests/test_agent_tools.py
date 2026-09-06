import pytest
from pydantic import ValidationError

from app.agent.tools.document_tools import (
    AddDocumentTool,
    DeleteDocumentTool,
    ReplaceDocumentTool,
)
from app.schemas.tools import (
    AddDocumentArgs,
    DeleteDocumentArgs,
    ReplaceDocumentArgs,
)


def test_add_document_tool_validates_arguments() -> None:
    tool = AddDocumentTool()

    result = tool.validate_args(
        {
            "file_name": "contract.pdf",
            "source_blob_path": "staging/contract.pdf",
        }
    )

    assert isinstance(result, AddDocumentArgs)
    assert result.file_name == "contract.pdf"
    assert result.source_blob_path == "staging/contract.pdf"


def test_replace_document_tool_validates_arguments() -> None:
    tool = ReplaceDocumentTool()

    result = tool.validate_args(
        {
            "file_name": "contract.pdf",
            "source_blob_path": "staging/replacement.pdf",
        }
    )

    assert isinstance(result, ReplaceDocumentArgs)


def test_delete_document_tool_validates_arguments() -> None:
    tool = DeleteDocumentTool()

    result = tool.validate_args(
        {
            "file_name": "contract.pdf",
        }
    )

    assert isinstance(result, DeleteDocumentArgs)


def test_add_document_tool_rejects_missing_source_blob_path() -> None:
    tool = AddDocumentTool()

    with pytest.raises(ValidationError):
        tool.validate_args(
            {
                "file_name": "contract.pdf",
            }
        )


def test_delete_document_tool_rejects_empty_file_name() -> None:
    tool = DeleteDocumentTool()

    with pytest.raises(ValidationError):
        tool.validate_args(
            {
                "file_name": "",
            }
        )


def test_delete_document_tool_rejects_unknown_fields() -> None:
    tool = DeleteDocumentTool()

    with pytest.raises(ValidationError):
        tool.validate_args(
            {
                "file_name": "contract.pdf",
                "force": True,
            }
        )


def test_to_openai_tool_builds_function_schema() -> None:
    from app.agent.tools.base import to_openai_tool

    tool = DeleteDocumentTool()

    schema = to_openai_tool(tool)

    assert schema["type"] == "function"

    function = schema["function"]

    assert isinstance(function, dict)
    assert function["name"] == "delete_document"
    assert function["description"] == "Delete an existing document"

    parameters = function["parameters"]

    assert isinstance(parameters, dict)
    assert parameters["type"] == "object"
    assert "file_name" in parameters["properties"]
    assert "file_name" in parameters["required"]
    assert parameters["additionalProperties"] is False


def test_search_documents_tool_executes_embedding_and_search() -> None:
    from unittest.mock import patch

    from app.agent.tools.search_tool import SearchDocumentsTool

    tool = SearchDocumentsTool()
    arguments = tool.validate_args(
        {
            "query": "What is the rent?",
            "file_name": "contract.pdf",
        }
    )

    expected_results = [
        {
            "content": "Monthly rent is 5,000 NIS",
            "file_name": "contract.pdf",
            "page": 2,
        }
    ]

    with (
        patch(
            "app.agent.tools.search_tool.create_query_embedding",
            return_value=[0.1, 0.2, 0.3],
        ) as mock_embedding,
        patch(
            "app.agent.tools.search_tool.hybrid_search",
            return_value=expected_results,
        ) as mock_search,
    ):
        result = tool.execute(arguments)

    mock_embedding.assert_called_once_with("What is the rent?")

    mock_search.assert_called_once_with(
        "What is the rent?",
        [0.1, 0.2, 0.3],
        file_name="contract.pdf",
        parent_document_id=None,
    )

    assert result == expected_results
