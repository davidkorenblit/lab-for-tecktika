import pytest
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError

from app.core.config import settings
from app.services.conversation_service import TableConversationStore


class FakeConversationTableClient:
    def __init__(self) -> None:
        self.entities: dict[tuple[str, str], dict[str, object]] = {}
        self.versions: dict[tuple[str, str], int] = {}

    class Entity(dict[str, object]):
        def __init__(
            self,
            entity: dict[str, object],
            version: int,
        ) -> None:
            super().__init__(entity)
            self.metadata = {"etag": str(version)}

    def create_entity(self, entity: dict[str, object]) -> None:
        key = (str(entity["PartitionKey"]), str(entity["RowKey"]))
        if key in self.entities:
            raise ResourceExistsError("Entity already exists")
        self.entities[key] = dict(entity)
        self.versions[key] = 1

    def get_entity(
        self,
        partition_key: str,
        row_key: str,
    ) -> Entity:
        try:
            key = (partition_key, row_key)
            return self.Entity(self.entities[key], self.versions[key])
        except KeyError as exc:
            raise ResourceNotFoundError("Entity not found") from exc

    def update_entity(
        self,
        entity: dict[str, object],
        **kwargs: object,
    ) -> None:
        key = (str(entity["PartitionKey"]), str(entity["RowKey"]))
        if key not in self.entities:
            raise ResourceNotFoundError("Entity not found")
        if str(kwargs.get("etag")) != str(self.versions[key]):
            from azure.core.exceptions import ResourceModifiedError

            raise ResourceModifiedError("ETag did not match")
        self.entities[key].update(entity)
        self.versions[key] += 1

    def query_entities(
        self,
        query_filter: str,
        **kwargs: object,
    ) -> list[dict[str, object]]:
        del query_filter
        parameters = kwargs.get("parameters")
        if not isinstance(parameters, dict):
            raise AssertionError("Expected parameterized Table query")
        partition_key = parameters["partition_key"]
        return [
            dict(entity)
            for (entity_partition, _), entity in self.entities.items()
            if entity_partition == partition_key
        ]


@pytest.fixture
def conversation_table_client() -> FakeConversationTableClient:
    return FakeConversationTableClient()


@pytest.fixture(autouse=True)
def enable_explicit_test_auth_bypass(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "environment", "test")
    monkeypatch.setattr(settings, "allow_local_auth_bypass", True)


@pytest.fixture(autouse=True)
def isolate_conversation_history(
    monkeypatch: pytest.MonkeyPatch,
    conversation_table_client: FakeConversationTableClient,
) -> None:
    from app.api.v1.endpoints import chat

    store = TableConversationStore(
        table_client_factory=lambda: conversation_table_client
    )
    monkeypatch.setattr(chat, "conversation_store", store)
