from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.file_resolver import resolve_document


def test_resolve_document_returns_exact_case_insensitive_match() -> None:
    blob = SimpleNamespace(
        name="Q3-report.pdf",
        metadata={"document_id": "doc_123"},
        etag='"etag_123"',
    )

    container = MagicMock()
    container.list_blobs.return_value = [blob]

    service = MagicMock()
    service.get_container_client.return_value = container

    with patch(
        "app.services.file_resolver.get_blob_service_client",
        return_value=service,
    ):
        matches = resolve_document("q3-REPORT.pdf")

    assert len(matches) == 1
    assert matches[0].file_name == "Q3-report.pdf"
    assert matches[0].document_id == "doc_123"
    assert matches[0].etag == '"etag_123"'


def test_resolve_document_returns_empty_when_not_found() -> None:
    blob = SimpleNamespace(
        name="other.pdf",
        metadata={"document_id": "doc_other"},
        etag='"etag_other"',
    )

    container = MagicMock()
    container.list_blobs.return_value = [blob]

    service = MagicMock()
    service.get_container_client.return_value = container

    with patch(
        "app.services.file_resolver.get_blob_service_client",
        return_value=service,
    ):
        matches = resolve_document("missing.pdf")

    assert matches == []
