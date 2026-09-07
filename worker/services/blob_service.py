import logging
import time
from typing import Optional
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

from config import settings


class BlobService:
    """
    Service for inspecting file metadata and ETags in Azure Blob Storage.
    """
    def __init__(self):
        self.account_url = f"https://{settings.STORAGE_ACCOUNT_NAME}.blob.core.windows.net"
        self.container_name = settings.BLOB_CONTAINER_NAME
        self._client: Optional[BlobServiceClient] = None

    def _get_client(self) -> BlobServiceClient:
        if not self._client:
            credential = DefaultAzureCredential()
            self._client = BlobServiceClient(account_url=self.account_url, credential=credential)
        return self._client

    def get_blob_etag(self, blob_name: str) -> Optional[str]:
        """
        Fetches the current ETag (version signature) of a file from Blob Storage.
        """
        try:
            client = self._get_client()
            blob_client = client.get_blob_client(container=self.container_name, blob=blob_name)
            properties = blob_client.get_blob_properties()
            return properties.etag
            
        except Exception as err:
            logging.error(f"Failed to fetch ETag for Blob '{blob_name}': {err}")
            return None

    def is_file_changed(self, blob_name: str, previous_etag: Optional[str]) -> bool:
        """
        Returns True if the file is new or modified. Returns False if unchanged (Idempotency check).
        """
        current_etag = self.get_blob_etag(blob_name)
        if not current_etag:
            return True  # If unable to fetch ETag, process to be safe

        if current_etag == previous_etag:
            logging.info(f"Blob '{blob_name}' unchanged (ETag match). Skipping processing.")
            return False

        return True

    def copy_from_staging(
        self,
        source_blob_path: str,
        target_blob_name: str,
        document_id: Optional[str] = None,
        max_wait_seconds: int = 60,
    ) -> bool:
        """
        Copies a blob from staging container to the primary documents container,
        sets document_id metadata, and awaits copy completion.
        """
        try:
            client = self._get_client()
            staging_container = getattr(settings, "STAGING_CONTAINER_NAME", "staging")
            source_container = staging_container
            source_blob_name = source_blob_path

            # Strip leading container prefix if present (e.g., 'staging/<fileId>/<name>')
            if source_blob_path.startswith(f"{staging_container}/"):
                source_blob_name = source_blob_path[len(staging_container) + 1 :]
            elif source_blob_path.startswith("staging/"):
                source_blob_name = source_blob_path[len("staging/") :]

            source_blob_client = client.get_blob_client(container=source_container, blob=source_blob_name)
            target_blob_client = client.get_blob_client(container=self.container_name, blob=target_blob_name)

            metadata = {"document_id": document_id} if document_id else None
            target_blob_client.start_copy_from_url(source_blob_client.url, metadata=metadata)
            logging.info(f"Initiated copy of '{source_blob_path}' to '{self.container_name}/{target_blob_name}'")

            # Await copy status completion
            start_time = time.time()
            while time.time() - start_time < max_wait_seconds:
                props = target_blob_client.get_blob_properties()
                copy_status = getattr(getattr(props, "copy", None), "status", None)
                if copy_status == "success":
                    logging.info(f"Successfully finished copy of '{target_blob_name}' with status 'success'")
                    if document_id:
                        target_blob_client.set_blob_metadata(metadata={"document_id": document_id})
                    return True
                elif copy_status in ("failed", "aborted"):
                    raise RuntimeError(f"Blob copy failed with status: {copy_status}")
                elif copy_status is None:
                    # In mock environments or immediate synchronous copy
                    if document_id:
                        try:
                            target_blob_client.set_blob_metadata(metadata={"document_id": document_id})
                        except Exception:
                            pass
                    return True
                time.sleep(0.5)

            raise TimeoutError(f"Blob copy timed out after {max_wait_seconds} seconds")
        except Exception as err:
            logging.error(f"Failed to copy '{source_blob_path}' to '{target_blob_name}': {err}")
            raise err

    def delete_blob(self, blob_name: str) -> bool:
        """
        Deletes a blob from the primary documents container if it exists.
        """
        try:
            client = self._get_client()
            blob_client = client.get_blob_client(container=self.container_name, blob=blob_name)
            if blob_client.exists():
                blob_client.delete_blob()
                logging.info(f"Successfully deleted blob '{blob_name}' from container '{self.container_name}'")
            return True
        except Exception as err:
            logging.warning(f"Failed to delete blob '{blob_name}' from container '{self.container_name}': {err}")
            return False
