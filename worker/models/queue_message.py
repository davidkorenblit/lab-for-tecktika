from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class EventType(str, Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class QueueMessage(BaseModel):
    """
    Data model for events arriving from the Storage Queue.
    """
    event_type: EventType = Field(..., description="CREATE, UPDATE, or DELETE")
    blob_name: str = Field(..., description="File name in Blob Storage")
    document_id: str = Field(..., description="Unique ParentDocumentID")
    etag: Optional[str] = Field(None, description="Blob ETag for version check")
