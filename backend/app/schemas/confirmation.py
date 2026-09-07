from pydantic import BaseModel, ConfigDict, Field

from app.schemas.jobs import JobOperation


class PendingConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    confirmation_id: str = Field(alias="confirmationId", min_length=1)
    action: JobOperation
    file_name: str = Field(alias="fileName", min_length=1)
    blob_name: str = Field(alias="blobName", min_length=1)
    document_id: str = Field(alias="documentId", min_length=1)
    requested_by: str = Field(alias="requestedBy", min_length=1)
    source_blob_path: str | None = Field(
        default=None,
        alias="sourceBlobPath",
    )
    etag: str | None = None
    completed: bool = False
    job_id: str | None = Field(default=None, alias="jobId")


class ConfirmActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    confirmation_id: str = Field(alias="confirmationId", min_length=1)
    confirmed: bool
    action: str = Field(min_length=1)
    files: list[str] = Field(min_length=1)


class ConfirmActionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    job_id: str | None = Field(default=None, alias="jobId")
    status: str
    message: str


class ConfirmationEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    confirmation_id: str = Field(alias="confirmationId", min_length=1)
    action: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    files: list[str] = Field(min_length=1)
    destructive: bool = True
