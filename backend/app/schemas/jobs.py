from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class JobOperation(str, Enum):
    ADD = "ADD"
    REPLACE = "REPLACE"
    DELETE = "DELETE"


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class QueueMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    job_id: UUID = Field(alias="jobId")
    operation: JobOperation
    file_name: str = Field(alias="fileName")
    blob_name: str = Field(alias="blobName")
    requested_by: str = Field(alias="requestedBy")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        alias="createdAt",
    )