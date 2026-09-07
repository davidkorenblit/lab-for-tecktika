from typing import Any

import pytest

from app.schemas.chat import Citation, MessageAttachment
from app.schemas.confirmation import ConfirmationEvent
from app.services.conversation_service import TableConversationStore


def _store(table_client: Any) -> TableConversationStore:
    return TableConversationStore(table_client_factory=lambda: table_client)


def test_history_survives_new_store_and_retains_chronological_order(
    conversation_table_client: Any,
) -> None:
    first_store = _store(conversation_table_client)
    first_store.add_message(
        conversation_id="conv_123",
        requested_by="user_123",
        role="user",
        content="What is the rent?",
    )
    first_store.add_message(
        conversation_id="conv_123",
        requested_by="user_123",
        role="assistant",
        content="The monthly rent is 5,000.",
    )

    second_store = _store(conversation_table_client)
    messages = second_store.get_messages("conv_123", "user_123")

    assert [message.role for message in messages] == ["user", "assistant"]
    assert [message.content for message in messages] == [
        "What is the rent?",
        "The monthly rent is 5,000.",
    ]


def test_message_metadata_survives_persistence(
    conversation_table_client: Any,
) -> None:
    store = _store(conversation_table_client)
    attachment = MessageAttachment(
        fileId="file_1",
        fileName="contract.pdf",
        size=1234,
        blobPath="staging/file_1.pdf",
    )
    citation = Citation(
        id="chunk_1",
        fileName="contract.pdf",
        page=2,
        snippet="Payment is due in 30 days.",
    )
    confirmation = ConfirmationEvent(
        confirmationId="cf_1",
        action="replace",
        summary="Replace contract.pdf?",
        files=["contract.pdf"],
    )
    store.add_message(
        conversation_id="conv_metadata",
        requested_by="owner",
        role="assistant",
        content="Please confirm.",
        attachments=[attachment],
        citations=[citation],
        confirmation=confirmation,
        job_ids=["job_1", "job_2"],
    )

    message = _store(conversation_table_client).get_messages(
        "conv_metadata", "owner"
    )[0]

    assert message.attachments == [attachment]
    assert message.citations == [citation]
    assert message.confirmation == confirmation
    assert message.job_ids == ["job_1", "job_2"]


def test_conversation_store_enforces_owner_for_read_and_append(
    conversation_table_client: Any,
) -> None:
    owner_store = _store(conversation_table_client)
    owner_store.add_message(
        conversation_id="conv_private",
        requested_by="owner",
        role="user",
        content="Private message",
    )
    other_store = _store(conversation_table_client)

    with pytest.raises(PermissionError):
        other_store.get_messages("conv_private", "other-user")

    with pytest.raises(PermissionError):
        other_store.add_message(
            conversation_id="conv_private",
            requested_by="other-user",
            role="user",
            content="Unauthorized append",
        )


def test_multiple_messages_never_overwrite_each_other(
    conversation_table_client: Any,
) -> None:
    store = _store(conversation_table_client)

    for index in range(10):
        store.add_message(
            conversation_id="conv_many",
            requested_by="owner",
            role="user",
            content=f"Message {index}",
        )

    messages = _store(conversation_table_client).get_messages(
        "conv_many", "owner"
    )
    assert len(messages) == 10
    assert [message.content for message in messages] == [
        f"Message {index}" for index in range(10)
    ]
    assert len({message.id for message in messages}) == 10
