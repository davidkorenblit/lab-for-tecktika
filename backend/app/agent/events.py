from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.confirmation import ConfirmationEvent


class AgentEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["delta", "confirmation"]
    delta: str | None = None
    confirmation: ConfirmationEvent | None = None
