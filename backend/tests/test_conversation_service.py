from app.services.conversation_service import (
    InMemoryConversationStore,
)


def test_conversation_store_saves_and_returns_messages() -> None:
    store = InMemoryConversationStore()

    store.add_message(
        conversation_id="conv_123",
        requested_by="user_123",
        role="user",
        content="What is the rent?",
    )

    store.add_message(
        conversation_id="conv_123",
        requested_by="user_123",
        role="assistant",
        content="The monthly rent is 5,000.",
    )

    messages = store.get_messages("conv_123", "user_123")

    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[0].content == "What is the rent?"
    assert messages[1].role == "assistant"
    assert messages[1].content == "The monthly rent is 5,000."


def test_conversation_store_rejects_another_user() -> None:
    store = InMemoryConversationStore()
    store.add_message(
        conversation_id="conv_private",
        requested_by="owner",
        role="user",
        content="Private message",
    )

    try:
        store.get_messages("conv_private", "other-user")
    except PermissionError:
        pass
    else:
        raise AssertionError("Cross-user conversation access was allowed")
