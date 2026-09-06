from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.data.tables import TableServiceClient
from azure.storage.queue import QueueServiceClient
from azure.storage.blob import BlobServiceClient
from azure.search.documents import SearchClient
from openai import AzureOpenAI
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

def get_search_client() -> SearchClient:
    return SearchClient(
        endpoint=settings.azure_search_endpoint,
        index_name=settings.azure_search_index_name,
        credential=credential,
    )

def get_openai_client() -> AzureOpenAI:
    token_provider = get_bearer_token_provider(
        credential,
        "https://cognitiveservices.azure.com/.default",
    )

    return AzureOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        api_version=settings.azure_openai_api_version,
        azure_ad_token_provider=token_provider,
    )

