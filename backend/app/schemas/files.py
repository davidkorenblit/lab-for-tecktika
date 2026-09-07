from pydantic import BaseModel, ConfigDict, Field


class UploadUrlRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    file_name: str = Field(alias="fileName", min_length=1)
    content_type: str = Field(alias="contentType", min_length=1)
    size: int = Field(gt=0, le=52_428_800)


class UploadUrlResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    upload_url: str = Field(alias="uploadUrl")
    file_id: str = Field(alias="fileId")
    blob_path: str = Field(alias="blobPath")
    expires_at: str = Field(alias="expiresAt")
