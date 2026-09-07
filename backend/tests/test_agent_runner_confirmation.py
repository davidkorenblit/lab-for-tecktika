from types import SimpleNamespace
from unittest.mock import patch

from app.agent.runner import stream_agent
from app.services.file_resolver import ResolvedDocument


def test_delete_tool_creates_confirmation_event() -> None:
    tool_call = SimpleNamespace(
        id="call_delete_1",
        function=SimpleNamespace(
            name="delete_document",
            arguments='{"file_name":"Q3-report.pdf"}',
        ),
    )

    assistant_message = SimpleNamespace(
        content=None,
        tool_calls=[tool_call],
    )

    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=assistant_message,
            )
        ]
    )

    resolved = ResolvedDocument(
        file_name="Q3-report.pdf",
        blob_name="Q3-report.pdf",
        document_id="doc_123",
        etag='"etag_123"',
    )

    with (
        patch(
            "app.agent.runner.create_chat_completion",
            return_value=response,
        ),
        patch(
            "app.agent.runner.resolve_document",
            return_value=[resolved],
        ),
        patch(
            "app.agent.runner.confirmation_store.create",
        ) as create_confirmation,
    ):
        create_confirmation.return_value = SimpleNamespace(
            confirmation_id="cf_test_123",
        )

        events = list(
            stream_agent(
                "Delete Q3-report.pdf",
                requested_by="conv_123",
            )
        )

    assert len(events) == 1

    event = events[0]

    assert event.type == "confirmation"
    assert event.confirmation is not None
    assert event.confirmation.confirmation_id == "cf_test_123"
    assert event.confirmation.action == "delete"
    assert event.confirmation.files == ["Q3-report.pdf"]
    assert event.confirmation.destructive is True

    create_confirmation.assert_called_once_with(
        action="DELETE",
        file_name="Q3-report.pdf",
        blob_name="Q3-report.pdf",
        document_id="doc_123",
        requested_by="conv_123",
        source_blob_path=None,
        etag='"etag_123"',
    )


def test_replace_tool_uses_trusted_staged_attachment() -> None:
    tool_call = SimpleNamespace(
        id="call_replace_1",
        function=SimpleNamespace(
            name="replace_document",
            arguments='{"file_name":"Q3-report.pdf"}',
        ),
    )

    assistant_message = SimpleNamespace(
        content=None,
        tool_calls=[tool_call],
    )

    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=assistant_message,
            )
        ]
    )

    resolved = ResolvedDocument(
        file_name="Q3-report.pdf",
        blob_name="Q3-report.pdf",
        document_id="doc_123",
        etag='"etag_123"',
    )

    with (
        patch(
            "app.agent.runner.create_chat_completion",
            return_value=response,
        ),
        patch(
            "app.agent.runner.resolve_document",
            return_value=[resolved],
        ),
        patch(
            "app.agent.runner.confirmation_store.create",
        ) as create_confirmation,
    ):
        create_confirmation.return_value = SimpleNamespace(
            confirmation_id="cf_replace_123",
        )

        events = list(
            stream_agent(
                "Replace Q3-report.pdf with the attached file",
                requested_by="conv_123",
                source_blob_path="staging/f_1.pdf",
            )
        )

    assert len(events) == 1

    event = events[0]

    assert event.type == "confirmation"
    assert event.confirmation is not None
    assert event.confirmation.confirmation_id == "cf_replace_123"
    assert event.confirmation.action == "replace"
    assert event.confirmation.files == ["Q3-report.pdf"]
    assert event.confirmation.destructive is True

    create_confirmation.assert_called_once()

    call = create_confirmation.call_args.kwargs

    assert call["file_name"] == "Q3-report.pdf"
    assert call["document_id"] == "doc_123"
    assert call["requested_by"] == "conv_123"
    assert call["source_blob_path"] == "staging/f_1.pdf"
