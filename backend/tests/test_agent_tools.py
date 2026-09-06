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
