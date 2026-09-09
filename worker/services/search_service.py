import logging
from typing import Optional
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexerClient

import time
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

    @staticmethod
    def _normalize_status(value) -> str:
        """
        Reduces an indexer status to a bare lowercase word.

        The SDK hands back an IndexerExecutionStatus enum, and str() on it
        yields 'IndexerExecutionStatus.IN_PROGRESS' - not 'inProgress'. The
        previous comparison against ('inprogress', 'running') therefore never
        matched, so a run that was simply still going was reported as a
        failure, and even a successful run would have been, since the success
        comparison had the same flaw.
        """
        raw = getattr(value, "value", value)
        text = str(raw)

        if "." in text:
            text = text.rsplit(".", 1)[-1]

        return text.replace("_", "").replace("-", "").lower()

    def wait_for_indexer(
        self,
        timeout_seconds: Optional[int] = None,
        poll_interval: Optional[int] = None
    ) -> bool:
        """
        Triggers indexer and polls until completion, failure, or timeout.
        """
        timeout = timeout_seconds or settings.INDEXER_POLL_TIMEOUT_SECONDS
        interval = poll_interval or settings.INDEXER_POLL_INTERVAL_SECONDS

        client = self._get_indexer_client()
        self.trigger_indexer()

        deadline = time.time() + timeout
        while time.time() < deadline:
            time.sleep(interval)
            status = client.get_indexer_status(self.indexer_name)
            last = getattr(status, "last_result", None)

            if not last:
                continue

            state = self._normalize_status(last.status)

            if state in ("inprogress", "running", "reset"):
                continue
            if state == "success":
                logging.info(f"Indexer '{self.indexer_name}' completed successfully.")
                return True

            raise RuntimeError(f"Indexer '{self.indexer_name}' failed with status [{last.status}]. Errors: {getattr(last, 'errors', None)}")

        raise TimeoutError(f"Indexer '{self.indexer_name}' timed out after {timeout} seconds.")

    def delete_document_chunks(self, document_id: str, file_name: Optional[str] = None) -> bool:
        """
        Executes surgical deletion by locating all chunks where parentDocumentId eq document_id
        or fileName eq file_name, and purging them from the search index.
        """
        try:
            client = self._get_search_client()
            escaped_doc_id = document_id.replace("'", "''") if document_id else ""
            conditions = []
            if escaped_doc_id:
                conditions.append(f"parentDocumentId eq '{escaped_doc_id}'")
            if file_name:
                escaped_file_name = file_name.replace("'", "''")
                conditions.append(f"fileName eq '{escaped_file_name}'")

            if not conditions:
                logging.warning("Neither document_id nor file_name provided for chunk deletion.")
                return True

            filter_query = " or ".join(conditions)

            # Step 1: Locate all chunk IDs belonging to this document
            results = client.search(search_text="*", filter=filter_query, select=["id"])
            chunks_to_delete = [{"id": doc["id"]} for doc in results]

            if not chunks_to_delete:
                logging.info(f"No chunks found matching: '{filter_query}'")
                return True

            # Step 2: Perform bulk surgical deletion
            client.delete_documents(documents=chunks_to_delete)
            logging.info(f"Surgically purged {len(chunks_to_delete)} chunks matching '{filter_query}'")
            return True
        except Exception as err:
            logging.error(f"Failed surgical deletion for Doc ID '{document_id}', file '{file_name}': {err}")
            raise err
