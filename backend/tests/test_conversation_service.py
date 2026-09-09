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
        blobPath="f_1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d/file_1.pdf",
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


def test_pending_attachment_round_trip(conversation_table_client: Any) -> None:
    store = _store(conversation_table_client)
    store.add_message(
        conversation_id="conv_att",
        requested_by="owner",
        role="user",
        content="here is a file",
    )
    store.set_pending_attachment(
        conversation_id="conv_att",
        requested_by="owner",
        blob_path="f_abc/report.pdf",
        file_name="report.pdf",
    )

    pending = _store(conversation_table_client).get_pending_attachment(
        "conv_att", "owner"
    )
    assert pending == ("f_abc/report.pdf", "report.pdf")

    _store(conversation_table_client).clear_pending_attachment("conv_att", "owner")

    assert (
        _store(conversation_table_client).get_pending_attachment("conv_att", "owner")
        is None
    )


def test_pending_attachment_is_overwritten_by_a_newer_one(
    conversation_table_client: Any,
) -> None:
    store = _store(conversation_table_client)
    store.add_message(
        conversation_id="conv_att2",
        requested_by="owner",
        role="user",
        content="first file",
    )
    store.set_pending_attachment(
        conversation_id="conv_att2",
        requested_by="owner",
        blob_path="f_1/a.pdf",
        file_name="a.pdf",
    )
    store.set_pending_attachment(
        conversation_id="conv_att2",
        requested_by="owner",
        blob_path="f_2/b.pdf",
        file_name="b.pdf",
    )

    assert store.get_pending_attachment("conv_att2", "owner") == (
        "f_2/b.pdf",
        "b.pdf",
    )


def test_pending_attachment_is_scoped_to_owner(
    conversation_table_client: Any,
) -> None:
    store = _store(conversation_table_client)
    store.add_message(
        conversation_id="conv_att3",
        requested_by="owner",
        role="user",
        content="a file",
    )
    store.set_pending_attachment(
        conversation_id="conv_att3",
        requested_by="owner",
        blob_path="f_1/a.pdf",
        file_name="a.pdf",
    )

    assert store.get_pending_attachment("conv_att3", "someone-else") is None


def test_clear_pending_attachment_without_one_is_a_no_op(
    conversation_table_client: Any,
) -> None:
    store = _store(conversation_table_client)
    store.add_message(
        conversation_id="conv_att4",
        requested_by="owner",
        role="user",
        content="no file here",
    )

    store.clear_pending_attachment("conv_att4", "owner")

    assert store.get_pending_attachment("conv_att4", "owner") is None
