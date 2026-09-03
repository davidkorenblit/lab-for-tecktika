import logging
from models.queue_message import QueueMessage, EventType
from services.job_service import JobService
from services.blob_service import BlobService
from services.search_service import SearchService


class EventDispatcher:
    """
    Dispatcher service that routes queue events to the appropriate handling logic.
    """
    def __init__(self):
        self.job_service = JobService()
        self.blob_service = BlobService()
        self.search_service = SearchService()

    def dispatch(self, event: QueueMessage) -> None:
        """
        Main entrypoint to process and route incoming queue events.
        """
        logging.info(f"Dispatching [{event.event_type}] event for Document ID: {event.document_id}")

        # 1. Update status to RUNNING in Table Storage
        self.job_service.mark_running(event.document_id, event.blob_name)

        # 2. Handle Indexing (CREATE / UPDATE / INDEX) with Idempotency check
        if event.event_type in (EventType.CREATE, EventType.UPDATE, EventType.INDEX):
            if not self.blob_service.is_file_changed(event.blob_name, event.etag):
                self.job_service.mark_succeeded(event.document_id, event.blob_name)
                return
            self._handle_index(event)

        # 3. Handle Surgical Deletion (DELETE)
        elif event.event_type == EventType.DELETE:
            self._handle_delete(event)

    def _handle_index(self, event: QueueMessage) -> None:
        """
        Triggers Azure AI Search indexer and marks job status as SUCCEEDED upon completion.
        """
        self.search_service.trigger_indexer()
        self.job_service.mark_succeeded(event.document_id, event.blob_name)
        logging.info(f"Indexing completed successfully for Doc ID: {event.document_id}")

    def _handle_delete(self, event: QueueMessage) -> None:
        """
        Triggers Azure AI Search surgical deletion (will be connected in PR 7).
        """
        logging.info(f"Deletion handler triggered for Doc ID: {event.document_id}")
