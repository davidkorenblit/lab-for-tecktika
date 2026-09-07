import hashlib
import json
from collections.abc import Callable, Iterable, Mapping
from typing import Any, Protocol
from uuid import uuid4

from azure.core import MatchConditions
from azure.core.exceptions import (
    ResourceExistsError,
    ResourceModifiedError,
    ResourceNotFoundError,
)

from app.azure_clients import get_table_service_client
from app.core.config import settings
from app.schemas.chat import ChatHistoryMessage, Citation, MessageAttachment
from app.schemas.confirmation import ConfirmationEvent


_CONVERSATION_PARTITION_PREFIX = "conversation-"
_METADATA_ROW_KEY = "metadata"
_MESSAGE_ROW_PREFIX = "message-"


class _ConversationTableClient(Protocol):
    def create_entity(self, entity: Mapping[str, Any]) -> Any: ...

    def get_entity(
        self,
        partition_key: str,
        row_key: str,
    ) -> Mapping[str, Any]: ...

    def query_entities(
        self,
        query_filter: str,
        **kwargs: Any,
    ) -> Iterable[Mapping[str, Any]]: ...

    def update_entity(
        self,
        entity: Mapping[str, Any],
        **kwargs: Any,
    ) -> Any: ...


class TableConversationStore:
    def __init__(
        self,
        table_client_factory: Callable[[], _ConversationTableClient] | None = None,
    ) -> None:
        self._table_client_factory = (
            table_client_factory or self._create_table_client
        )

    @staticmethod
    def _create_table_client() -> _ConversationTableClient:
        service_client = get_table_service_client()
        return service_client.get_table_client(
            table_name=(
                settings.conversation_history_table_name
                or settings.job_status_table_name
            ),
        )

    @staticmethod
    def _partition_key(conversation_id: str) -> str:
        digest = hashlib.sha256(conversation_id.encode("utf-8")).hexdigest()
        return f"{_CONVERSATION_PARTITION_PREFIX}{digest}"

    @staticmethod
    def _metadata_entity(
        *,
        partition_key: str,
        conversation_id: str,
        requested_by: str,
    ) -> dict[str, Any]:
        return {
            "PartitionKey": partition_key,
            "RowKey": _METADATA_ROW_KEY,
            "entityType": "conversation",
            "conversationId": conversation_id,
            "requestedBy": requested_by,
            "nextSequence": 0,
        }

    @staticmethod
    def _assert_owner(
        entity: Mapping[str, Any],
        conversation_id: str,
        requested_by: str,
    ) -> None:
        if entity.get("requestedBy") != requested_by:
            raise PermissionError(conversation_id)

    def _ensure_owner(
        self,
        *,
        table_client: _ConversationTableClient,
        partition_key: str,
        conversation_id: str,
        requested_by: str,
    ) -> None:
        try:
            metadata = table_client.get_entity(
                partition_key=partition_key,
                row_key=_METADATA_ROW_KEY,
            )
        except ResourceNotFoundError:
            metadata = self._metadata_entity(
                partition_key=partition_key,
                conversation_id=conversation_id,
                requested_by=requested_by,
            )
            try:
                table_client.create_entity(entity=metadata)
            except ResourceExistsError:
                metadata = table_client.get_entity(
                    partition_key=partition_key,
                    row_key=_METADATA_ROW_KEY,
                )

        self._assert_owner(metadata, conversation_id, requested_by)

    def _claim_sequence(
        self,
        *,
        table_client: _ConversationTableClient,
        partition_key: str,
        conversation_id: str,
        requested_by: str,
    ) -> int:
        for _ in range(10):
            metadata = table_client.get_entity(
                partition_key=partition_key,
                row_key=_METADATA_ROW_KEY,
            )
            self._assert_owner(metadata, conversation_id, requested_by)
            sequence = int(metadata.get("nextSequence", 0))
            table_metadata = getattr(metadata, "metadata", {})
            etag = table_metadata.get("etag")
            if not etag:
                raise RuntimeError(
                    "Azure Table conversation metadata did not contain an ETag"
                )

            try:
                table_client.update_entity(
                    entity={
                        "PartitionKey": partition_key,
                        "RowKey": _METADATA_ROW_KEY,
                        "nextSequence": sequence + 1,
                    },
                    mode="merge",
                    etag=etag,
                    match_condition=MatchConditions.IfNotModified,
                )
            except ResourceModifiedError:
                continue
            return sequence

        raise RuntimeError(
            "Could not reserve a conversation message sequence"
        )

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
        table_client = self._table_client_factory()
        partition_key = self._partition_key(conversation_id)
        self._ensure_owner(
            table_client=table_client,
            partition_key=partition_key,
            conversation_id=conversation_id,
            requested_by=requested_by,
        )
        sequence = self._claim_sequence(
            table_client=table_client,
            partition_key=partition_key,
            conversation_id=conversation_id,
            requested_by=requested_by,
        )

        message = ChatHistoryMessage(
            id=f"msg_{uuid4().hex}",
            role=role,
            content=content,
            attachments=attachments or [],
            citations=citations or [],
            confirmation=confirmation,
            jobIds=job_ids or [],
        )
        entity = {
            "PartitionKey": partition_key,
            "RowKey": f"{_MESSAGE_ROW_PREFIX}{sequence:020d}",
            "entityType": "message",
            "requestedBy": requested_by,
            "messageJson": json.dumps(
                message.model_dump(by_alias=True, mode="json"),
                separators=(",", ":"),
            ),
        }
        table_client.create_entity(entity=entity)
        return message

    def get_messages(
        self,
        conversation_id: str,
        requested_by: str,
    ) -> list[ChatHistoryMessage]:
        table_client = self._table_client_factory()
        partition_key = self._partition_key(conversation_id)
        try:
            metadata = table_client.get_entity(
                partition_key=partition_key,
                row_key=_METADATA_ROW_KEY,
            )
        except ResourceNotFoundError:
            return []

        self._assert_owner(metadata, conversation_id, requested_by)
        entities = table_client.query_entities(
            query_filter="PartitionKey eq @partition_key",
            parameters={"partition_key": partition_key},
        )
        message_entities = sorted(
            (
                entity
                for entity in entities
                if entity.get("entityType") == "message"
            ),
            key=lambda entity: str(entity["RowKey"]),
        )
        return [
            ChatHistoryMessage.model_validate_json(str(entity["messageJson"]))
            for entity in message_entities
        ]
