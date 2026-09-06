import os


class Settings:
    """
    Centralized configuration settings read from App Settings / Environment variables.
    """
    # Azure Storage Account & Resources (aligned with infrastructure Bicep appSettings)
    AZURE_STORAGE_ACCOUNT_NAME: str = (
        os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
        or os.getenv("STORAGE_ACCOUNT_NAME")
        or "stragpocdevqelri355piqlq"
    )
    STORAGE_ACCOUNT_NAME: str = AZURE_STORAGE_ACCOUNT_NAME

    STORAGE_QUEUE_NAME: str = (
        os.getenv("STORAGE_QUEUE_NAME")
        or os.getenv("JOBS_QUEUE_NAME")
        or "index-jobs"
    )
    JOBS_QUEUE_NAME: str = STORAGE_QUEUE_NAME

    POISON_QUEUE_NAME: str = os.getenv("POISON_QUEUE_NAME", f"{STORAGE_QUEUE_NAME}-poison")

    JOB_STATUS_TABLE_NAME: str = (
        os.getenv("JOB_STATUS_TABLE_NAME")
        or os.getenv("JOBS_TABLE_NAME")
        or "jobstatus"
    )
    JOBS_TABLE_NAME: str = JOB_STATUS_TABLE_NAME

    BLOB_CONTAINER_NAME: str = os.getenv("BLOB_CONTAINER_NAME", "pdf-library")

    # Azure AI Services Endpoints
    AZURE_SEARCH_ENDPOINT: str = os.getenv(
        "AZURE_SEARCH_ENDPOINT",
        "https://srch-ragpoc-dev-qelri355piqlq.search.windows.net"
    )
    AZURE_OPENAI_ENDPOINT: str = os.getenv(
        "AZURE_OPENAI_ENDPOINT",
        "https://aoai-ragpoc-dev-qelri355piqlq.openai.azure.com/"
    )

    # Search Pipeline Names (supports both backend and worker env naming)
    SEARCH_INDEX_NAME: str = (
        os.getenv("AZURE_SEARCH_INDEX_NAME")
        or os.getenv("AZURE_SEARCH_INDEX")
        or "pdf-chunks-index"
    )
    SEARCH_INDEXER_NAME: str = (
        os.getenv("AZURE_SEARCH_INDEXER_NAME")
        or os.getenv("AZURE_SEARCH_INDEXER")
        or "pdf-chunks-indexer"
    )
    SEARCH_SKILLSET_NAME: str = (
        os.getenv("AZURE_SEARCH_SKILLSET_NAME")
        or os.getenv("AZURE_SEARCH_SKILLSET")
        or "pdf-chunks-skillset"
    )
    SEARCH_DATASOURCE_NAME: str = (
        os.getenv("AZURE_SEARCH_DATASOURCE_NAME")
        or os.getenv("AZURE_SEARCH_DATASOURCE")
        or "pdf-blob-datasource"
    )
    OPENAI_EMBEDDING_DEPLOYMENT: str = os.getenv("OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")
    INDEXER_POLL_TIMEOUT_SECONDS: int = int(os.getenv("INDEXER_POLL_TIMEOUT_SECONDS", "120"))
    INDEXER_POLL_INTERVAL_SECONDS: int = int(os.getenv("INDEXER_POLL_INTERVAL_SECONDS", "3"))


settings = Settings()
