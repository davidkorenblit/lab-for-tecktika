import os
import logging
from typing import Optional

from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes import SearchIndexClient, SearchIndexerClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SimpleField,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
    SearchIndexerDataSourceConnection,
    SearchIndexerDataContainer,
    SearchIndexerSkillset,
    SplitSkill,
    InputFieldMappingEntry,
    OutputFieldMappingEntry,
    AzureOpenAIEmbeddingSkill,
    SearchIndexer,
    FieldMapping,
    IndexingParameters,
    SearchIndexerIndexProjections,
    SearchIndexerIndexProjectionSelector,
    SearchIndexerIndexProjectionsParameters,
    IndexProjectionMode,
)

from config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class SearchPipelineSetupService:
    """
    Idempotent setup service for Azure AI Search data-plane resources:
    - Data Source Connection (Blob Storage)
    - Search Index (with HNSW vector profile and corrected schema)
    - Skillset (Text splitting with overlap + Azure OpenAI embeddings)
    - Search Indexer (Connecting source, skillset, and target index)
    """

    def __init__(
        self,
        endpoint: Optional[str] = None,
        index_name: Optional[str] = None,
        indexer_name: Optional[str] = None,
        skillset_name: Optional[str] = None,
        datasource_name: Optional[str] = None,
        openai_endpoint: Optional[str] = None,
        embedding_deployment: Optional[str] = None,
        storage_account_name: Optional[str] = None,
        blob_container_name: Optional[str] = None,
    ):
        self.endpoint = endpoint or settings.AZURE_SEARCH_ENDPOINT
        self.index_name = index_name or settings.SEARCH_INDEX_NAME
        self.indexer_name = indexer_name or settings.SEARCH_INDEXER_NAME
        self.skillset_name = skillset_name or settings.SEARCH_SKILLSET_NAME
        self.datasource_name = datasource_name or settings.SEARCH_DATASOURCE_NAME
        self.openai_endpoint = openai_endpoint or settings.AZURE_OPENAI_ENDPOINT
        self.embedding_deployment = embedding_deployment or settings.OPENAI_EMBEDDING_DEPLOYMENT
        self.storage_account_name = storage_account_name or settings.STORAGE_ACCOUNT_NAME
        self.blob_container_name = blob_container_name or settings.BLOB_CONTAINER_NAME

        self.credential = DefaultAzureCredential()
        self.index_client = SearchIndexClient(endpoint=self.endpoint, credential=self.credential)
        self.indexer_client = SearchIndexerClient(endpoint=self.endpoint, credential=self.credential)

    def create_or_update_datasource(self) -> SearchIndexerDataSourceConnection:
        """
        Idempotently creates or updates the Blob Storage data source connection.
        Uses Managed Identity connection string format if no explicit connection string is provided.
        """
        logging.info(f"Setting up Data Source: '{self.datasource_name}'...")

        # If a connection string is explicitly passed via environment, use it;
        # otherwise use Managed Identity ResourceId connection string.
        storage_conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        if not storage_conn_str:
            # Managed Identity connection string format for Azure AI Search -> Blob
            subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID", "")
            resource_group = os.getenv("AZURE_RESOURCE_GROUP", "rg-sharepoint-rag-dev")
            if subscription_id:
                storage_conn_str = (
                    f"ResourceId=/subscriptions/{subscription_id}/resourceGroups/{resource_group}"
                    f"/providers/Microsoft.Storage/storageAccounts/{self.storage_account_name};"
                )
            else:
                # Standard Managed Identity connection string fallback
                storage_conn_str = f"ResourceId=/providers/Microsoft.Storage/storageAccounts/{self.storage_account_name};"

        data_source = SearchIndexerDataSourceConnection(
            name=self.datasource_name,
            type="azureblob",
            connection_string=storage_conn_str,
            container=SearchIndexerDataContainer(name=self.blob_container_name),
            description="Blob storage container for PDF library ingestion",
        )

        result = self.indexer_client.create_or_update_data_source_connection(data_source)
        logging.info(f"✓ Data Source '{result.name}' successfully configured.")
        return result

    def create_or_update_index(self) -> SearchIndex:
        """
        Idempotently creates or updates the Search Index with:
        - 1536 vector dimensions with HNSW algorithm
        - Corrected field names: 'parentDocumentId', 'fileName'
        - Added missing fields: 'page', 'sourceUrl'
        """
        logging.info(f"Setting up Search Index: '{self.index_name}'...")

        fields = [
            SimpleField(
                name="id",
                type=SearchFieldDataType.STRING,
                key=True,
                filterable=True,
                sortable=True,
            ),
            SimpleField(
                name="parentDocumentId",
                type=SearchFieldDataType.STRING,
                filterable=True,
                sortable=True,
            ),
            SearchableField(
                name="fileName",
                type=SearchFieldDataType.STRING,
                filterable=True,
                sortable=True,
            ),
            SimpleField(
                name="page",
                type=SearchFieldDataType.INT32,
                filterable=True,
                sortable=True,
            ),
            SimpleField(
                name="sourceUrl",
                type=SearchFieldDataType.STRING,
                filterable=False,
            ),
            SearchableField(
                name="content",
                type=SearchFieldDataType.STRING,
            ),
            SearchField(
                name="text_vector",
                type=SearchFieldDataType.COLLECTION(SearchFieldDataType.SINGLE),
                searchable=True,
                vector_search_dimensions=1536,
                vector_search_profile_name="hnsw-profile",
            ),
        ]

        vector_search = VectorSearch(
            algorithms=[
                HnswAlgorithmConfiguration(
                    name="hnsw-algorithm",
                )
            ],
            profiles=[
                VectorSearchProfile(
                    name="hnsw-profile",
                    algorithm_configuration_name="hnsw-algorithm",
                )
            ],
        )

        index = SearchIndex(
            name=self.index_name,
            fields=fields,
            vector_search=vector_search,
        )

        result = self.index_client.create_or_update_index(index)
        logging.info(f"✓ Search Index '{result.name}' successfully configured.")
        return result

    def create_or_update_skillset(self) -> SearchIndexerSkillset:
        """
        Idempotently creates or updates the Skillset with:
        - SplitSkill: Splits PDF text into pages with overlap
        - AzureOpenAIEmbeddingSkill: Vectorizes chunks with text-embedding-3-small (1536d)
        """
        logging.info(f"Setting up Skillset: '{self.skillset_name}'...")

        split_skill = SplitSkill(
            name="split-skill",
            description="Splits document content into pages with overlap",
            context="/document",
            text_split_mode="pages",
            maximum_page_length=2000,
            page_overlap_length=500,
            inputs=[
                InputFieldMappingEntry(name="text", source="/document/content"),
            ],
            outputs=[
                OutputFieldMappingEntry(name="textItems", target_name="pages"),
            ],
        )

        # Support both resource_url and resource_uri depending on Azure SDK version
        skill_kwargs = {
            "name": "openai-embedding-skill",
            "description": "Generates text embeddings using Azure OpenAI text-embedding-3-small",
            "context": "/document/pages/*",
            "deployment_name": self.embedding_deployment,
            "model_name": "text-embedding-3-small",
            "inputs": [
                InputFieldMappingEntry(name="text", source="/document/pages/*"),
            ],
            "outputs": [
                OutputFieldMappingEntry(name="embedding", target_name="text_vector"),
            ],
        }
        openai_key = os.getenv("AZURE_OPENAI_KEY") or os.getenv("AZURE_OPENAI_API_KEY")
        if openai_key:
            skill_kwargs["api_key"] = openai_key

        try:
            embedding_skill = AzureOpenAIEmbeddingSkill(resource_url=self.openai_endpoint, **skill_kwargs)
        except TypeError:
            embedding_skill = AzureOpenAIEmbeddingSkill(resource_uri=self.openai_endpoint, **skill_kwargs)

        index_projections = SearchIndexerIndexProjections(
            selectors=[
                SearchIndexerIndexProjectionSelector(
                    target_index_name=self.index_name,
                    parent_key_field_name="parentDocumentId",
                    source_context="/document/pages/*",
                    mappings=[
                        InputFieldMappingEntry(name="content", source="/document/pages/*"),
                        InputFieldMappingEntry(name="text_vector", source="/document/pages/*/text_vector"),
                        InputFieldMappingEntry(name="fileName", source="/document/metadata_storage_name"),
                        InputFieldMappingEntry(name="sourceUrl", source="/document/metadata_storage_path"),
                    ],
                )
            ],
            parameters=SearchIndexerIndexProjectionsParameters(
                projection_mode=IndexProjectionMode.SKIP_INDEXING_PARENT_DOCUMENTS
            ),
        )

        skillset_kwargs = {
            "name": self.skillset_name,
            "description": "Skillset for PDF page splitting and OpenAI vector embedding",
            "skills": [split_skill, embedding_skill],
        }
        try:
            skillset = SearchIndexerSkillset(index_projections=index_projections, **skillset_kwargs)
        except TypeError:
            skillset = SearchIndexerSkillset(index_projection=index_projections, **skillset_kwargs)

        result = self.indexer_client.create_or_update_skillset(skillset)
        logging.info(f"✓ Skillset '{result.name}' successfully configured.")
        return result

    def create_or_update_indexer(self) -> SearchIndexer:
        """
        Idempotently creates or updates the Search Indexer connecting
        the DataSource, Skillset, and Index.
        Uses Skillset IndexProjections to project 1-to-N page chunks into the index,
        skipping parent documents.
        """
        logging.info(f"Setting up Indexer: '{self.indexer_name}'...")

        parameters = IndexingParameters(
            configuration={
                "dataToExtract": "contentAndMetadata",
                "parsingMode": "default",
            }
        )

        indexer = SearchIndexer(
            name=self.indexer_name,
            description="Indexer for continuous/on-demand PDF library indexing with integrated vectorization",
            data_source_name=self.datasource_name,
            target_index_name=self.index_name,
            skillset_name=self.skillset_name,
            field_mappings=[],
            output_field_mappings=[],
            parameters=parameters,
        )

        result = self.indexer_client.create_or_update_indexer(indexer)
        logging.info(f"✓ Indexer '{result.name}' successfully configured.")
        return result

    def setup_pipeline(self):
        """
        Executes complete idempotent setup for all 4 pipeline components in order:
        1. DataSourceConnection
        2. Index
        3. Skillset
        4. Indexer
        """
        logging.info("==================================================")
        logging.info("Starting Azure AI Search Pipeline Setup...")
        logging.info(f"Endpoint: {self.endpoint}")
        logging.info(f"Index: {self.index_name}")
        logging.info(f"Indexer: {self.indexer_name}")
        logging.info(f"Skillset: {self.skillset_name}")
        logging.info(f"DataSource: {self.datasource_name}")
        logging.info("==================================================")

        self.create_or_update_datasource()
        self.create_or_update_index()
        self.create_or_update_skillset()
        self.create_or_update_indexer()

        logging.info("==================================================")
        logging.info("✓ Azure AI Search Pipeline successfully configured!")
        logging.info("==================================================")


if __name__ == "__main__":
    service = SearchPipelineSetupService()
    service.setup_pipeline()
