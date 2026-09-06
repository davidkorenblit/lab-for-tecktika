from pydantic import BaseModel, ConfigDict, Field


class AddDocumentArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_name: str = Field(
        ...,
        min_length=1,
        description="Exact name of the document to add",
    )
    source_blob_path: str = Field(
        ...,
        min_length=1,
        description="Path of the staged source blob",
    )


class ReplaceDocumentArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_name: str = Field(
        ...,
        min_length=1,
        description="Exact name of the document to replace",
    )
    source_blob_path: str = Field(
        ...,
        min_length=1,
        description="Path of the staged replacement blob",
    )


class DeleteDocumentArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_name: str = Field(
        ...,
        min_length=1,
        description="Exact name of the document to delete",
    )
