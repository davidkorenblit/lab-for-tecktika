from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class JobEntity(BaseModel):
    """
    Data model for tracking status records in Azure Table Storage.
    """
    PartitionKey: str = Field(default="ingestion-jobs")
    RowKey: str = Field(..., description="Document ID / Job ID")
    status: JobStatus = Field(default=JobStatus.QUEUED)
    blob_name: str = Field(...)
    etag: Optional[str] = Field(default=None)
    error_message: Optional[str] = Field(default=None)
