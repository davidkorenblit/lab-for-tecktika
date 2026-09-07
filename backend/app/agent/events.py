from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.confirmation import ConfirmationEvent


class JobEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    job_id: str = Field(alias="jobId")
    status: str
    file_name: str = Field(alias="fileName")


class AgentEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["delta", "confirmation", "job"]
    delta: str | None = None
    confirmation: ConfirmationEvent | None = None
    job: JobEvent | None = None
