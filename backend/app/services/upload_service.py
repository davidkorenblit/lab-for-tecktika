from datetime import datetime, timedelta, timezone
from uuid import uuid4

from azure.storage.blob import (
    BlobSasPermissions,
    generate_blob_sas,
)

from app.azure_clients import get_blob_service_client
from app.core.config import settings


def create_upload_url(
    file_name: str,
    content_type: str,
    size: int,
) -> dict[str, str]:
    if not settings.azure_storage_account_name:
        raise ValueError("Azure Storage account is not configured")

    if not settings.staging_container_name:
        raise ValueError("Staging container is not configured")

    file_id = f"f_{uuid4().hex}"
    blob_path = f"{file_id}/{file_name}"

    now = datetime.now(timezone.utc)
    starts_on = now - timedelta(minutes=5)
    expires_on = now + timedelta(minutes=15)

    service_client = get_blob_service_client()

    delegation_key = service_client.get_user_delegation_key(
        key_start_time=starts_on,
        key_expiry_time=expires_on,
    )

    sas = generate_blob_sas(
        account_name=settings.azure_storage_account_name,
        container_name=settings.staging_container_name,
        blob_name=blob_path,
        user_delegation_key=delegation_key,
        permission=BlobSasPermissions(write=True, create=True),
        start=starts_on,
        expiry=expires_on,
    )

    upload_url = (
        f"https://{settings.azure_storage_account_name}"
        f".blob.core.windows.net/"
        f"{settings.staging_container_name}/{blob_path}?{sas}"
    )

    return {
        "uploadUrl": upload_url,
        "fileId": file_id,
        "blobPath": blob_path,
        "expiresAt": expires_on.isoformat(),
    }
