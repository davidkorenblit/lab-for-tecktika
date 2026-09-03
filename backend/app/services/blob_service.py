from app.azure_clients import get_blob_service_client
from app.core.config import settings


def upload_document(
    blob_name: str,
    data: bytes,
    document_id: str,
):
    service_client = get_blob_service_client()

    container_client = service_client.get_container_client(
        settings.azure_blob_container_documents
    )

    blob_client = container_client.get_blob_client(blob_name)

    blob_client.upload_blob(
        data,
        overwrite=False,
        metadata={
            "document_id": document_id,
        },
    )

    properties = blob_client.get_blob_properties()

    return properties.etag