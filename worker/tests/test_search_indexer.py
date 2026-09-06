from unittest.mock import MagicMock, patch
import pytest

from services.search_indexer import SearchPipelineSetupService


@patch("services.search_indexer.SearchIndexerClient")
@patch("services.search_indexer.SearchIndexClient")
@patch("services.search_indexer.DefaultAzureCredential")
def test_search_pipeline_setup(MockCredential, MockIndexClient, MockIndexerClient):
    """
    Verifies that SearchPipelineSetupService idempotently creates or updates:
    1. Data Source Connection
    2. Index with proper schema (parentDocumentId, fileName, page, sourceUrl, text_vector 1536d)
    3. Skillset with SplitSkill and OpenAIEmbeddingSkill
    4. Indexer with field mappings
    """
    mock_index_client = MockIndexClient.return_value
    mock_indexer_client = MockIndexerClient.return_value

    mock_indexer_client.create_or_update_data_source_connection.return_value = MagicMock(name="pdf-blob-datasource")
    mock_index_client.create_or_update_index.return_value = MagicMock(name="pdf-chunks-index")
    mock_indexer_client.create_or_update_skillset.return_value = MagicMock(name="pdf-chunks-skillset")
    mock_indexer_client.create_or_update_indexer.return_value = MagicMock(name="pdf-chunks-indexer")

    service = SearchPipelineSetupService()
    service.setup_pipeline()

    # Verify DataSource creation
    mock_indexer_client.create_or_update_data_source_connection.assert_called_once()
    ds_arg = mock_indexer_client.create_or_update_data_source_connection.call_args[0][0]
    assert ds_arg.name == service.datasource_name
    assert ds_arg.type == "azureblob"
    assert ds_arg.container.name == service.blob_container_name

    # Verify Index schema
    mock_index_client.create_or_update_index.assert_called_once()
    index_arg = mock_index_client.create_or_update_index.call_args[0][0]
    assert index_arg.name == service.index_name
    field_names = [f.name for f in index_arg.fields]
    assert "id" in field_names
    assert "parentDocumentId" in field_names
    assert "fileName" in field_names
    assert "page" in field_names
    assert "sourceUrl" in field_names
    assert "content" in field_names
    assert "text_vector" in field_names

    # Check vector field dimensions
    vector_field = next(f for f in index_arg.fields if f.name == "text_vector")
    assert vector_field.vector_search_dimensions == 1536
    assert vector_field.vector_search_profile_name == "hnsw-profile"

    # Verify Skillset
    mock_indexer_client.create_or_update_skillset.assert_called_once()
    skillset_arg = mock_indexer_client.create_or_update_skillset.call_args[0][0]
    assert skillset_arg.name == service.skillset_name
    assert len(skillset_arg.skills) == 2
    assert skillset_arg.skills[0].text_split_mode == "pages"
    assert skillset_arg.skills[1].deployment_name == service.embedding_deployment

    # Verify Indexer
    mock_indexer_client.create_or_update_indexer.assert_called_once()
    indexer_arg = mock_indexer_client.create_or_update_indexer.call_args[0][0]
    assert indexer_arg.name == service.indexer_name
    assert indexer_arg.target_index_name == service.index_name
    assert indexer_arg.skillset_name == service.skillset_name
