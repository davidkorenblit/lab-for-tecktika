from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.validation import validate_file_name


class AddDocumentArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_name: str = Field(
        ...,
        min_length=1,
        description="Exact name of the attached document to add",
    )

    @field_validator("file_name")
    @classmethod
    def _check_file_name(cls, value: str) -> str:
        return validate_file_name(value)



class ReplaceDocumentArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_name: str = Field(
        ...,
        min_length=1,
        description="Exact name of the existing document to replace",
    )

    @field_validator("file_name")
    @classmethod
    def _check_file_name(cls, value: str) -> str:
        return validate_file_name(value)



class DeleteDocumentArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_name: str = Field(
        ...,
        min_length=1,
        description="Exact name of the document to delete",
    )

    @field_validator("file_name")
    @classmethod
    def _check_file_name(cls, value: str) -> str:
        return validate_file_name(value)



class SearchDocumentsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(
        ...,
        min_length=1,
        description="Question or search query to run against the indexed documents",
    )
    file_name: str | None = Field(
        default=None,
        description="Optional exact file name to restrict the search",
    )
    parent_document_id: str | None = Field(
        default=None,
        description="Optional document ID to restrict the search",
    )


class ListDocumentsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

