from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.validation import (
    validate_file_name,
    validate_staged_blob_path,
)
from app.schemas.confirmation import ConfirmationEvent


class MessageAttachment(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )

    file_id: str = Field(alias="fileId", min_length=1)
    file_name: str = Field(alias="fileName", min_length=1)
    size: int = Field(ge=0)
    blob_path: str = Field(alias="blobPath", min_length=1)

    # Both of these are echoed back by the client and then reach the model and
    # Blob Storage, so they are validated at the edge rather than at each use.
    @field_validator("file_name")
    @classmethod
    def _check_file_name(cls, value: str) -> str:
        return validate_file_name(value)

    @field_validator("blob_path")
    @classmethod
    def _check_blob_path(cls, value: str) -> str:
        return validate_staged_blob_path(value)


class ChatMessageRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )

    message: str = Field(min_length=1)
    conversation_id: str | None = Field(
        default=None,
        alias="conversationId",
    )
    stream: bool = True
    attachments: list[MessageAttachment] = Field(
        default_factory=list
    )


class Citation(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )

    id: str = Field(min_length=1)
    file_name: str = Field(alias="fileName", min_length=1)
    title: str | None = None
    url: str | None = None
    page: int | None = None
    snippet: str | None = None
    score: float | None = None


class ChatHistoryMessage(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )

    id: str = Field(min_length=1)
    role: str = Field(min_length=1)
    content: str
    citations: list[Citation] = Field(default_factory=list)
    attachments: list[MessageAttachment] = Field(default_factory=list)
    confirmation: ConfirmationEvent | None = None
    job_ids: list[str] = Field(default_factory=list, alias="jobIds")


class ChatHistoryResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )

    conversation_id: str = Field(
        alias="conversationId",
        min_length=1,
    )
    messages: list[ChatHistoryMessage] = Field(
        default_factory=list
    )
