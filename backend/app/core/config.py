from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application
    app_name: str = "Backend Agent API"
    environment: str = "local"
    cors_allowed_origins: str = "http://localhost:5173"

    # Azure AI Search
    azure_search_endpoint: str = ""
    azure_search_index_name: str = ""
    azure_search_semantic_configuration_name: str = ""

    # Azure AI Search schema fields
    aas_field_chunk_id: str = "chunkId"
    aas_field_parent_document_id: str = "parentDocumentId"
    aas_field_file_name: str = "fileName"
    aas_field_content: str = "content"
    aas_field_page: str = "page"
    aas_field_source_url: str = "sourceUrl"
    aas_field_vector: str = "text_vector"

    # Azure OpenAI
    azure_openai_endpoint: str = ""
    azure_openai_api_version: str = ""
    openai_chat_deployment: str = ""
    openai_embedding_deployment: str = ""

    # Azure Storage
    azure_storage_account_name: str = ""

    # Blob Storage
    blob_container_name: str = ""
    staging_container_name: str = ""

    # Queue Storage
    storage_queue_name: str = ""

    # Table Storage
    job_status_table_name: str = ""

    # Job statuses
    job_status_queued: str = "QUEUED"
    job_status_running: str = "RUNNING"
    job_status_succeeded: str = "SUCCEEDED"
    job_status_failed: str = "FAILED"

    # App authorization
    auth_default_role: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()