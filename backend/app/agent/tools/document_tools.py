from app.agent.tools.base import BaseTool
from app.schemas.tools import (
    AddDocumentArgs,
    DeleteDocumentArgs,
    ReplaceDocumentArgs,
)


class AddDocumentTool(BaseTool[AddDocumentArgs]):
    name = "add_document"
    description = "Add a new document from staging"
    args_schema = AddDocumentArgs

    def execute(
        self,
        arguments: AddDocumentArgs,
    ) -> object:
        raise NotImplementedError


class ReplaceDocumentTool(BaseTool[ReplaceDocumentArgs]):
    name = "replace_document"
    description = "Replace an existing document using a staged file"
    args_schema = ReplaceDocumentArgs

    def execute(
        self,
        arguments: ReplaceDocumentArgs,
    ) -> object:
        raise NotImplementedError


class DeleteDocumentTool(BaseTool[DeleteDocumentArgs]):
    name = "delete_document"
    description = "Delete an existing document"
    args_schema = DeleteDocumentArgs

    def execute(
        self,
        arguments: DeleteDocumentArgs,
    ) -> object:
        raise NotImplementedError
