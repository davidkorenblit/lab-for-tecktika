from dataclasses import dataclass

from app.azure_clients import get_blob_service_client
from app.core.config import settings


@dataclass(frozen=True)
class ResolvedDocument:
    file_name: str
    blob_name: str
    document_id: str
    etag: str | None


def resolve_document(file_name: str) -> list[ResolvedDocument]:
    if not file_name.strip():
        raise ValueError("file_name must not be empty")

    service_client = get_blob_service_client()
    container_client = service_client.get_container_client(
        settings.blob_container_name
    )

    matches: list[ResolvedDocument] = []

    for blob in container_client.list_blobs(
        include=["metadata"]
    ):
        blob_name = str(blob.name)

        if blob_name.casefold() != file_name.casefold():
            continue

        metadata = blob.metadata or {}
        document_id = metadata.get("document_id")

        if not document_id:
            continue

        matches.append(
            ResolvedDocument(
                file_name=blob_name,
                blob_name=blob_name,
                document_id=document_id,
                etag=str(blob.etag) if blob.etag else None,
            )
        )

    return matches
