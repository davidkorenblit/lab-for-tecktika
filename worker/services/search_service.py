import logging
from typing import Optional
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexerClient

from config import settings


class SearchService:
    """
    Service for interacting with Azure AI Search Indexer and Index queries.
    """
    def __init__(self):
        self.endpoint = settings.AZURE_SEARCH_ENDPOINT
        self.index_name = settings.SEARCH_INDEX_NAME
        self.indexer_name = settings.SEARCH_INDEXER_NAME
        self._indexer_client: Optional[SearchIndexerClient] = None
        self._search_client: Optional[SearchClient] = None

    def _get_indexer_client(self) -> SearchIndexerClient:
        if not self._indexer_client:
            credential = DefaultAzureCredential()
            self._indexer_client = SearchIndexerClient(endpoint=self.endpoint, credential=credential)
        return self._indexer_client

    def _get_search_client(self) -> SearchClient:
        if not self._search_client:
            credential = DefaultAzureCredential()
            self._search_client = SearchClient(
                endpoint=self.endpoint,
                index_name=self.index_name,
                credential=credential
            )
        return self._search_client

    def trigger_indexer(self) -> bool:
        """
        Triggers an on-demand execution of the Azure AI Search Indexer.
        """
        try:
            client = self._get_indexer_client()
            client.run_indexer(self.indexer_name)
            logging.info(f"Successfully triggered Azure AI Search Indexer: '{self.indexer_name}'")
            return True
        except Exception as err:
            logging.error(f"Failed to trigger Azure AI Search Indexer '{self.indexer_name}': {err}")
            raise err

    def delete_document_chunks(self, document_id: str) -> bool:
        """
        Executes surgical deletion by locating all chunks where ParentDocumentID eq document_id
        and purging them from the search index.
        """
        try:
            client = self._get_search_client()
            filter_query = f"ParentDocumentID eq '{document_id}'"
            
            # Step 1: Locate all chunk IDs belonging to this ParentDocumentID
            results = client.search(search_text="*", filter=filter_query, select=["id"])
            chunks_to_delete = [{"id": doc["id"]} for doc in results]

            if not chunks_to_delete:
                logging.info(f"No chunks found for ParentDocumentID: '{document_id}'")
                return True

            # Step 2: Perform bulk surgical deletion
            client.delete_documents(documents=chunks_to_delete)
            logging.info(f"Surgically purged {len(chunks_to_delete)} chunks for Doc ID: '{document_id}'")
            return True
        except Exception as err:
            logging.error(f"Failed surgical deletion for Doc ID '{document_id}': {err}")
            raise err
