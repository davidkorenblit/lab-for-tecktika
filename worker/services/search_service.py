import logging
from typing import Optional
from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes import SearchIndexerClient

from config import settings


class SearchService:
    """
    Service for interacting with Azure AI Search Indexer and Index queries.
    """
    def __init__(self):
        self.endpoint = settings.AZURE_SEARCH_ENDPOINT
        self.indexer_name = settings.SEARCH_INDEXER_NAME
        self._indexer_client: Optional[SearchIndexerClient] = None

    def _get_indexer_client(self) -> SearchIndexerClient:
        if not self._indexer_client:
            credential = DefaultAzureCredential()
            self._indexer_client = SearchIndexerClient(endpoint=self.endpoint, credential=credential)
        return self._indexer_client

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
