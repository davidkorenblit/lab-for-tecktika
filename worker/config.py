import os


class Settings:
    """
    Centralized configuration settings read from App Settings / Environment variables.
    """
    # Azure Storage resources
    JOBS_QUEUE_NAME: str = os.getenv("JOBS_QUEUE_NAME", "index-jobs")
    POISON_QUEUE_NAME: str = os.getenv("POISON_QUEUE_NAME", "index-jobs-poison")
    JOBS_TABLE_NAME: str = os.getenv("JOBS_TABLE_NAME", "jobstatus")
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

    # Search Pipeline Names
    SEARCH_INDEX_NAME: str = os.getenv("AZURE_SEARCH_INDEX", "pdf-chunks-index")
    SEARCH_INDEXER_NAME: str = os.getenv("AZURE_SEARCH_INDEXER", "pdf-chunks-indexer")


settings = Settings()
