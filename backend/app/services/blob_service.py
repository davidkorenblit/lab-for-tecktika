from app.azure_clients import get_blob_service_client
from app.core.config import settings


def upload_document(
    blob_name: str,
    data: bytes,
    document_id: str,
) -> tuple[str, str]:
    """
    Uploads a document to the staging container only.
    The Backend does NOT upload or copy directly to the primary documents container;
    the Worker takes care of non-blocking copy and indexing asynchronously.

    Returns:
        tuple[str, str]: (etag, source_blob_path)
    """
    staging_container = settings.staging_container_name
    service_client = get_blob_service_client()
    container_client = service_client.get_container_client(staging_container)
    blob_client = container_client.get_blob_client(blob_name)

    blob_client.upload_blob(
        data,
        overwrite=True,
        metadata={
            "document_id": document_id,
        },
    )

    properties = blob_client.get_blob_properties()
    source_blob_path = f"{staging_container}/{blob_name}"

    return properties.etag, source_blob_path