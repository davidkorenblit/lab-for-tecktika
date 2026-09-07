from uuid import uuid4

from app.schemas.chat import ChatHistoryMessage


class InMemoryConversationStore:
    def __init__(self) -> None:
        self._messages: dict[str, list[ChatHistoryMessage]] = {}

    def add_message(
        self,
        *,
        conversation_id: str,
        role: str,
        content: str,
    ) -> ChatHistoryMessage:
        message = ChatHistoryMessage(
            id=f"msg_{uuid4().hex}",
            role=role,
            content=content,
        )

        self._messages.setdefault(
            conversation_id,
            [],
        ).append(message)

        return message

    def get_messages(
        self,
        conversation_id: str,
    ) -> list[ChatHistoryMessage]:
        return list(
            self._messages.get(
                conversation_id,
                [],
            )
        )