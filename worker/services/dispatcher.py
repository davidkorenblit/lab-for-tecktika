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
        logging.info(f"Dispatching [{event.event_type}] event for Job ID: {event.job_id}, Doc ID: {event.document_id}")

        # 1. Update status to RUNNING in Table Storage
        self.job_service.mark_running(event.job_id, event.document_id, event.blob_name)

        # 2. If source_blob_path provided, copy from staging to documents container
        if getattr(event, "source_blob_path", None) and event.event_type in (EventType.CREATE, EventType.UPDATE):
            logging.info(f"Copying staging blob '{event.source_blob_path}' to documents '{event.blob_name}'")
            self.blob_service.copy_from_staging(event.source_blob_path, event.blob_name)

        # 3. Handle Indexing (CREATE / UPDATE) with Idempotency check
        if event.event_type == EventType.UPDATE:
            if not self.blob_service.is_file_changed(event.blob_name, event.etag):
                self.job_service.mark_succeeded(event.job_id, event.document_id, event.blob_name)
                return
            self._handle_index(event)
        elif event.event_type == EventType.CREATE:
            self._handle_index(event)

        # 4. Handle Surgical Deletion (DELETE)
        elif event.event_type == EventType.DELETE:
            self._handle_delete(event)

    def _handle_index(self, event: QueueMessage) -> None:
        """
        Triggers Azure AI Search indexer and awaits completion. If updating, purges old chunks first to ensure zero ghost chunks.
        """
        try:
            if event.event_type == EventType.UPDATE:
                logging.info(f"UPDATE event detected: purging old chunks for Doc ID: {event.document_id}")
                self.search_service.delete_document_chunks(event.document_id)

            self.search_service.wait_for_indexer()
            self.job_service.mark_succeeded(event.job_id, event.document_id, event.blob_name)
            logging.info(f"Indexing completed successfully for Job ID: {event.job_id}, Doc ID: {event.document_id}")
        except Exception as err:
            logging.error(f"Indexing failed for Job ID: {event.job_id}: {err}")
            self.job_service.mark_failed(event.job_id, event.document_id, event.blob_name, error_msg=str(err))
            raise err

    def _handle_delete(self, event: QueueMessage) -> None:
        """
        Executes surgical deletion of all chunks for Document ID, removes blob from storage, and updates status to SUCCEEDED.
        """
        try:
            self.search_service.delete_document_chunks(event.document_id)
            self.blob_service.delete_blob(event.blob_name)
            self.job_service.mark_succeeded(event.job_id, event.document_id, event.blob_name)
            logging.info(f"Surgical deletion completed successfully for Job ID: {event.job_id}, Doc ID: {event.document_id}")
        except Exception as err:
            logging.error(f"Surgical deletion failed for Job ID: {event.job_id}: {err}")
            self.job_service.mark_failed(event.job_id, event.document_id, event.blob_name, error_msg=str(err))
            raise err
