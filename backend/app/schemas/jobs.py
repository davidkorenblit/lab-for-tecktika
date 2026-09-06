from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class JobOperation(str, Enum):
    ADD = "ADD"
    REPLACE = "REPLACE"
    DELETE = "DELETE"


class EventType(str, Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class QueueMessage(BaseModel):
    """
    Message contract shared with the Worker.
    """

    job_id: str = Field(..., description="Unique Job ID for task tracking")
    event_type: EventType = Field(..., description="CREATE, UPDATE, or DELETE")
    blob_name: str = Field(..., description="File name in Blob Storage")
    document_id: str = Field(..., description="Unique ParentDocumentID")
    etag: str | None = Field(default=None)
    source_blob_path: str | None = Field(
        default=None,
        description="Optional path of the staged source blob",
    )


class CreateJobRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    operation: JobOperation
    file_name: str = Field(alias="fileName")
    blob_name: str = Field(alias="blobName")
    requested_by: str = Field(alias="requestedBy")


class JobEntity(BaseModel):
    """
    Data model for tracking job status in Azure Table Storage.
    """

    PartitionKey: str = Field(default="ingestion-jobs")
    RowKey: str = Field(..., description="Unique Job ID")

    document_id: str = Field(..., description="Unique Document ID")
    status: JobStatus = Field(default=JobStatus.QUEUED)
    blob_name: str = Field(...)

    etag: str | None = Field(default=None)
    error_message: str | None = Field(default=None)