from app.schemas.chat import ChatMessageRequest


def test_chat_message_request_accepts_frontend_contract() -> None:
    payload = {
        "message": "replace the vendor agreement with this",
        "conversationId": "conv_123",
        "stream": True,
        "attachments": [
            {
                "fileId": "f_1",
                "fileName": "vendor-2025.pdf",
                "size": 52428800,
                "blobPath": "staging/f_1.pdf",
            }
        ],
    }

    request = ChatMessageRequest.model_validate(payload)

    assert request.message == "replace the vendor agreement with this"
    assert request.conversation_id == "conv_123"
    assert request.stream is True
    assert len(request.attachments) == 1
    assert request.attachments[0].file_id == "f_1"
    assert request.attachments[0].file_name == "vendor-2025.pdf"
    assert request.attachments[0].blob_path == "staging/f_1.pdf"


def test_chat_history_response_accepts_frontend_contract() -> None:
    from app.schemas.chat import ChatHistoryResponse

    payload = {
        "conversationId": "conv_123",
        "messages": [
            {
                "id": "msg_1",
                "role": "user",
                "content": "What is the rent?",
                "attachments": [
                    {
                        "fileId": "f_1",
                        "fileName": "contract.pdf",
                        "size": 100,
                        "blobPath": "staging/f_1.pdf",
                    }
                ],
            },
            {
                "id": "msg_2",
                "role": "assistant",
                "content": "The monthly rent is 5,000.",
                "citations": [
                    {
                        "id": "chunk_88",
                        "fileName": "contract.pdf",
                        "page": 11,
                        "snippet": "Monthly rent is 5,000.",
                    }
                ],
                "confirmation": {
                    "confirmationId": "cf_1",
                    "action": "delete",
                    "summary": "Delete contract.pdf?",
                    "files": ["contract.pdf"],
                    "destructive": True,
                },
                "jobIds": ["job_1"],
            },
        ],
    }

    history = ChatHistoryResponse.model_validate(payload)

    assert history.conversation_id == "conv_123"
    assert len(history.messages) == 2
    assert history.messages[0].role == "user"
    assert history.messages[0].attachments[0].file_id == "f_1"
    assert history.messages[1].role == "assistant"
    assert history.messages[1].citations[0].file_name == "contract.pdf"
    assert history.messages[1].confirmation is not None
    assert history.messages[1].confirmation.confirmation_id == "cf_1"
    assert history.messages[1].job_ids == ["job_1"]
