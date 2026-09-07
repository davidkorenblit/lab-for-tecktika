from pydantic import BaseModel, ConfigDict, Field


class AddDocumentArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_name: str = Field(
        ...,
        min_length=1,
        description="Exact name of the attached document to add",
    )


class ReplaceDocumentArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_name: str = Field(
        ...,
        min_length=1,
        description="Exact name of the existing document to replace",
    )


class DeleteDocumentArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_name: str = Field(
        ...,
        min_length=1,
        description="Exact name of the document to delete",
    )


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
