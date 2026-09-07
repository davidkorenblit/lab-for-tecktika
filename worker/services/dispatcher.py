import logging
from models.queue_message import QueueMessage, EventType
from models.job_entity import JobStatus
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

        # 0. Idempotency check: Ignore duplicate delivery for terminal jobs
        current_status = self.job_service.get_job_status(event.job_id)
        if current_status in (JobStatus.SUCCEEDED, JobStatus.FAILED):
            logging.info(f"Job {event.job_id} already in terminal state '{current_status}'. Skipping duplicate processing.")
            return

        # 1. Update status to RUNNING in Table Storage
        self.job_service.mark_running(event.job_id, event.document_id, event.blob_name)

        # 2. Idempotency check for UPDATE before mutating the blob
        if event.event_type == EventType.UPDATE:
            if event.etag and not self.blob_service.is_file_changed(event.blob_name, event.etag):
                logging.info(f"UPDATE event skipped: Blob '{event.blob_name}' unchanged (ETag match).")
                self.job_service.mark_succeeded(event.job_id, event.document_id, event.blob_name)
                return

        # 3. If source_blob_path provided, copy from staging to documents container
        if getattr(event, "source_blob_path", None) and event.event_type in (EventType.CREATE, EventType.UPDATE):
            logging.info(f"Copying staging blob '{event.source_blob_path}' to documents '{event.blob_name}'")
            self.blob_service.copy_from_staging(
                source_blob_path=event.source_blob_path,
                target_blob_name=event.blob_name,
                document_id=event.document_id,
            )

        # 4. Handle Indexing (CREATE / UPDATE)
        if event.event_type in (EventType.CREATE, EventType.UPDATE):
            self._handle_index(event)

        # 5. Handle Surgical Deletion (DELETE)
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
