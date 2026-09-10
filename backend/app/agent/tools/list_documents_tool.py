from app.agent.tools.base import BaseTool
from app.schemas.tools import ListDocumentsArgs
from app.services.file_resolver import list_library_documents


class ListDocumentsTool(BaseTool[ListDocumentsArgs]):
    name = "list_documents"
    description = (
        "List all document file names currently stored and available in the library"
    )
    args_schema = ListDocumentsArgs

    def execute(
        self,
        arguments: ListDocumentsArgs,
    ) -> list[str]:
        return list_library_documents()
