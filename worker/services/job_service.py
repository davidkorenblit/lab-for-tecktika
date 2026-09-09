import logging
from typing import Optional
from azure.identity import DefaultAzureCredential
from azure.data.tables import TableClient

from config import settings
from models.job_entity import JobEntity, JobStatus


class JobService:
    """
    Service for writing job status updates to Azure Table Storage.
    """
    def __init__(self):
        self.table_url = f"https://{settings.STORAGE_ACCOUNT_NAME}.table.core.windows.net"
        self.table_name = settings.JOBS_TABLE_NAME
        self._client: Optional[TableClient] = None

    def _get_client(self) -> TableClient:
        if not self._client:
            credential = DefaultAzureCredential()
            self._client = TableClient(
                endpoint=self.table_url,
                table_name=self.table_name,
                credential=credential
            )
        return self._client

    def mark_status(self, job_id: str, document_id: str, blob_name: str, status: JobStatus, error_msg: Optional[str] = None) -> None:
        """
        Base method to update job status in Table Storage.
        """
        try:
            client = self._get_client()
            job = JobEntity(
                RowKey=job_id,
                document_id=document_id,
                blob_name=blob_name,
                status=status,
                error_message=error_msg
            )
            # mode="json" so the status is written as "FAILED" rather than the
            # enum member, which the Tables SDK stringifies to
            # "JobStatus.FAILED". That value is what the SPA polls on, and it
            # also broke this service's own get_job_status() idempotency read.
            client.upsert_entity(entity=job.model_dump(mode="json", exclude_none=True))
            logging.info(f"Table Storage updated: [{status}] for Job ID: {job_id} (Doc ID: {document_id})")
        except Exception as err:
            logging.error(f"Failed to update Table Storage for Job ID {job_id}: {err}")

    def get_job_status(self, job_id: str) -> Optional[JobStatus]:
        """
        Fetches current status of a job from Table Storage for idempotency check.
        """
        try:
            client = self._get_client()
            entity = client.get_entity(partition_key="ingestion-jobs", row_key=job_id)
            status_val = entity.get("status")
            return JobStatus(status_val) if status_val else None
        except Exception:
            return None

    def mark_running(self, job_id: str, document_id: str, blob_name: str) -> None:
        self.mark_status(job_id, document_id, blob_name, JobStatus.RUNNING)

    def mark_succeeded(self, job_id: str, document_id: str, blob_name: str) -> None:
        self.mark_status(job_id, document_id, blob_name, JobStatus.SUCCEEDED)

    def mark_failed(self, job_id: str, document_id: str, blob_name: str, error_msg: str) -> None:
        self.mark_status(job_id, document_id, blob_name, JobStatus.FAILED, error_msg=error_msg)
