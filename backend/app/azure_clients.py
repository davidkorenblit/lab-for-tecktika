from azure.identity import DefaultAzureCredential
from azure.data.tables import TableServiceClient
from azure.storage.queue import QueueServiceClient
from azure.storage.blob import BlobServiceClient
from app.core.config import settings


credential = DefaultAzureCredential()


def get_table_service_client() -> TableServiceClient:
    account_url = (
        f"https://{settings.azure_storage_account_name}.table.core.windows.net"
    )

    return TableServiceClient(
        endpoint=account_url,
        credential=credential,
    )


def get_queue_service_client() -> QueueServiceClient:
    account_url = (
        f"https://{settings.azure_storage_account_name}.queue.core.windows.net"
    )

    return QueueServiceClient(
        account_url=account_url,
        credential=credential,
    )

def get_blob_service_client() -> BlobServiceClient:
    account_url = (
        f"https://{settings.azure_storage_account_name}.blob.core.windows.net"
    )

    return BlobServiceClient(
        account_url=account_url,
        credential=credential,
    )