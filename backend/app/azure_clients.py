from azure.identity import DefaultAzureCredential
from azure.data.tables import TableServiceClient

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