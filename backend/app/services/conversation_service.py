from uuid import uuid4

from app.schemas.chat import (
    ChatHistoryMessage,
    Citation,
    MessageAttachment,
)
from app.schemas.confirmation import ConfirmationEvent


class InMemoryConversationStore:
    def __init__(self) -> None:
        self._messages: dict[str, list[ChatHistoryMessage]] = {}
        self._owners: dict[str, str] = {}

    def clear(self) -> None:
        self._messages.clear()
        self._owners.clear()

    def add_message(
        self,
        *,
        conversation_id: str,
        requested_by: str,
        role: str,
        content: str,
        attachments: list[MessageAttachment] | None = None,
        citations: list[Citation] | None = None,
        confirmation: ConfirmationEvent | None = None,
        job_ids: list[str] | None = None,
    ) -> ChatHistoryMessage:
        owner = self._owners.setdefault(conversation_id, requested_by)
        if owner != requested_by:
            raise PermissionError(conversation_id)

        message = ChatHistoryMessage(
            id=f"msg_{uuid4().hex}",
            role=role,
            content=content,
            attachments=attachments or [],
            citations=citations or [],
            confirmation=confirmation,
            jobIds=job_ids or [],
        )

        self._messages.setdefault(
            conversation_id,
            [],
        ).append(message)

        return message

    def get_messages(
        self,
        conversation_id: str,
        requested_by: str,
    ) -> list[ChatHistoryMessage]:
        owner = self._owners.get(conversation_id)
        if owner is not None and owner != requested_by:
            raise PermissionError(conversation_id)

        return list(
            self._messages.get(
                conversation_id,
                [],
            )
        )
