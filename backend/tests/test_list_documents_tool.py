from unittest.mock import MagicMock, patch
from types import SimpleNamespace

from app.agent.runner import stream_agent, run_agent, _build_messages
from app.agent.tools.list_documents_tool import ListDocumentsTool
from app.schemas.tools import ListDocumentsArgs
from app.schemas.chat import ChatHistoryMessage, MessageAttachment
from app.services.file_resolver import list_library_documents


def test_list_documents_tool_properties_and_execution() -> None:
    tool = ListDocumentsTool()
    assert tool.name == "list_documents"
    assert "List all document" in tool.description

    with patch(
        "app.agent.tools.list_documents_tool.list_library_documents",
        return_value=["file1.pdf", "file2.pdf"],
    ) as mock_list:
        result = tool.execute(ListDocumentsArgs())
        assert result == ["file1.pdf", "file2.pdf"]
        mock_list.assert_called_once()


def test_list_library_documents_queries_blob_container() -> None:
    blob1 = SimpleNamespace(name="doc_a.pdf")
    blob2 = SimpleNamespace(name="doc_b.pdf")
    blob3 = SimpleNamespace(name="doc_a.pdf")  # duplicate check

    mock_container = MagicMock()
    mock_container.list_blobs.return_value = [blob1, blob2, blob3]

    mock_service = MagicMock()
    mock_service.get_container_client.return_value = mock_container

    with patch(
        "app.services.file_resolver.get_blob_service_client",
        return_value=mock_service,
    ):
        docs = list_library_documents()

    assert docs == ["doc_a.pdf", "doc_b.pdf"]


def test_stream_agent_handles_list_documents_call() -> None:
    tool_call = SimpleNamespace(
        id="call_list",
        function=SimpleNamespace(
            name="list_documents",
            arguments="{}",
        ),
    )
    first_response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    role="assistant",
                    content=None,
                    tool_calls=[tool_call],
                )
            )
        ]
    )

    with (
        patch(
            "app.agent.runner.create_chat_completion",
            return_value=first_response,
        ),
        patch(
            "app.agent.runner.stream_chat_completion",
            return_value=iter(["These are your files: doc1.pdf"]),
        ),
        patch(
            "app.agent.tools.list_documents_tool.list_library_documents",
            return_value=["doc1.pdf"],
        ),
    ):
        events = list(
            stream_agent(
                "What documents are in the library?",
                requested_by="user_123",
            )
        )

    deltas = [e.delta for e in events if e.type == "delta"]
    assert "These are your files: doc1.pdf" in deltas


def test_run_agent_handles_list_documents_call() -> None:
    tool_call = SimpleNamespace(
        id="call_list_sync",
        function=SimpleNamespace(
            name="list_documents",
            arguments="{}",
        ),
    )
    first_response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    role="assistant",
                    content=None,
                    tool_calls=[tool_call],
                )
            )
        ]
    )
    final_response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    role="assistant",
                    content="Found 1 file: doc1.pdf",
                    tool_calls=None,
                )
            )
        ]
    )

    with (
        patch(
            "app.agent.runner.create_chat_completion",
            side_effect=[first_response, final_response],
        ),
        patch(
            "app.agent.tools.list_documents_tool.list_library_documents",
            return_value=["doc1.pdf"],
        ),
    ):
        answer = run_agent(
            "List my files",
        )

    assert answer == "Found 1 file: doc1.pdf"


def test_build_messages_includes_attachment_names_from_history() -> None:
    history = [
        ChatHistoryMessage(
            id="msg_1",
            role="user",
            content="Please index this",
            attachments=[
                MessageAttachment(
                    file_id="f_1",
                    file_name="policy.pdf",
                    size=1024,
                    blob_path="f_1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d/policy.pdf",
                )
            ],
        ),
        ChatHistoryMessage(
            id="msg_2",
            role="assistant",
            content="הקובץ 'policy.pdf' נוסף לספרייה ונשלח לאינדוקס.",
        ),
    ]



    messages = _build_messages(
        user_message="What is the policy details?",
        history=history,
    )

    # Verify that the user message in history retained the attachment file name
    user_hist_msg = next(m for m in messages if m["role"] == "user" and "policy.pdf" in str(m["content"]))
    assert "קובץ מצורף: policy.pdf" in user_hist_msg["content"]
