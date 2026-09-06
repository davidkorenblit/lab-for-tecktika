from app.agent.tools.base import BaseTool
from app.schemas.tools import SearchDocumentsArgs
from app.services.azure_openai import create_query_embedding
from app.services.azure_search import hybrid_search


class SearchDocumentsTool(BaseTool[SearchDocumentsArgs]):
    name = "search_documents"
    description = (
        "Search indexed documents and return relevant document chunks"
    )
    args_schema = SearchDocumentsArgs

    def execute(
        self,
        arguments: SearchDocumentsArgs,
    ) -> object:
        query_vector = create_query_embedding(arguments.query)

        return hybrid_search(
            arguments.query,
            query_vector,
            file_name=arguments.file_name,
            parent_document_id=arguments.parent_document_id,
        )
