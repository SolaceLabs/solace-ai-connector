"""Unit tests for LangChainVectorStoreEmbeddingsIndex."""

import pytest
from unittest.mock import patch, MagicMock

from solace_ai_connector.components.general.llm.langchain.langchain_vector_store_embedding_index import (
    LangChainVectorStoreEmbeddingsIndex,
    info,
)
from solace_ai_connector.components.general.llm.langchain.langchain_vector_store_embedding_base import (
    LangChainVectorStoreEmbeddingsBase,
)


class TestLangChainVectorStoreEmbeddingsIndex:
    """Tests for the LangChainVectorStoreEmbeddingsIndex class."""

    def test_initialization(self):
        """Test that LangChainVectorStoreEmbeddingsIndex initializes correctly."""
        with patch.object(
            LangChainVectorStoreEmbeddingsBase, "__init__", return_value=None
        ) as mock_init:
            # Initialize the component
            component = LangChainVectorStoreEmbeddingsIndex(config={})

            # Verify it's an instance of the base class
            assert isinstance(component, LangChainVectorStoreEmbeddingsBase)

            # Verify __init__ was called with the correct parameters
            mock_init.assert_called_once_with(info, config={})

    def test_info_dictionary(self):
        """Test that the info dictionary is properly defined."""
        # Verify the class name and description
        assert info["class_name"] == "LangChainVectorStoreEmbeddingsIndex"
        assert "index" in info["description"].lower()

        # Verify it contains all the necessary keys
        assert "input_schema" in info
        assert "output_schema" in info
        assert "config_parameters" in info

        # Verify the input schema has the required properties
        assert "texts" in info["input_schema"]["properties"]
        assert "metadatas" in info["input_schema"]["properties"]
        assert "ids" in info["input_schema"]["properties"]
        assert "action" in info["input_schema"]["properties"]
        assert info["input_schema"]["required"] == ["texts"]

        # Verify the output schema has the required properties
        assert "results" in info["output_schema"]["required"]

    def test_invoke_add_data_single_text(self, mock_message_fixture):
        """Test invoke method with add action and single text."""
        with patch.object(
            LangChainVectorStoreEmbeddingsBase, "__init__", return_value=None
        ) as mock_init:
            component = LangChainVectorStoreEmbeddingsIndex(config={})
            component.vector_store = MagicMock()

            # Call invoke with a single text
            data = {"texts": "This is a test text", "action": "add"}
            result = component.invoke(mock_message_fixture, data)

            # Verify the vector store's add_texts method was called
            component.vector_store.add_texts.assert_called_once_with(
                ["This is a test text"], ids=None
            )

            # Verify the result
            assert result == {"result": "OK"}

    def test_invoke_add_data_multiple_texts(self, mock_message_fixture):
        """Test invoke method with add action and multiple texts."""
        with patch.object(
            LangChainVectorStoreEmbeddingsBase, "__init__", return_value=None
        ) as mock_init:
            component = LangChainVectorStoreEmbeddingsIndex(config={})
            component.vector_store = MagicMock()

            # Call invoke with multiple texts
            data = {"texts": ["Text 1", "Text 2"], "action": "add"}
            result = component.invoke(mock_message_fixture, data)

            # Verify the vector store's add_texts method was called
            component.vector_store.add_texts.assert_called_once_with(
                ["Text 1", "Text 2"], ids=None
            )

            # Verify the result
            assert result == {"result": "OK"}

    def test_invoke_add_data_with_metadata(self, mock_message_fixture):
        """Test invoke method with add action and metadata."""
        with patch.object(
            LangChainVectorStoreEmbeddingsBase, "__init__", return_value=None
        ) as mock_init:
            component = LangChainVectorStoreEmbeddingsIndex(config={})
            component.vector_store = MagicMock()

            # Call invoke with metadata
            data = {
                "texts": ["Text 1", "Text 2"],
                "metadatas": [{"source": "source1"}, {"source": "source2"}],
                "action": "add",
            }
            result = component.invoke(mock_message_fixture, data)

            # Verify the vector store's add_texts method was called
            component.vector_store.add_texts.assert_called_once_with(
                ["Text 1", "Text 2"],
                [{"source": "source1"}, {"source": "source2"}],
                ids=None,
            )

            # Verify the result
            assert result == {"result": "OK"}

    def test_invoke_add_data_with_single_metadata(self, mock_message_fixture):
        """Test invoke method with add action and single metadata for multiple texts."""
        with patch.object(
            LangChainVectorStoreEmbeddingsBase, "__init__", return_value=None
        ) as mock_init:
            component = LangChainVectorStoreEmbeddingsIndex(config={})
            component.vector_store = MagicMock()

            # Call invoke with single metadata for multiple texts
            data = {
                "texts": ["Text 1", "Text 2"],
                "metadatas": {"source": "common_source"},
                "action": "add",
            }
            result = component.invoke(mock_message_fixture, data)

            # Verify the vector store's add_texts method was called
            component.vector_store.add_texts.assert_called_once_with(
                ["Text 1", "Text 2"],
                [{"source": "common_source"}, {"source": "common_source"}],
                ids=None,
            )

            # Verify the result
            assert result == {"result": "OK"}

    def test_invoke_add_data_with_ids(self, mock_message_fixture):
        """Test invoke method with add action and IDs."""
        with patch.object(
            LangChainVectorStoreEmbeddingsBase, "__init__", return_value=None
        ) as mock_init:
            component = LangChainVectorStoreEmbeddingsIndex(config={})
            component.vector_store = MagicMock()

            # Call invoke with IDs
            data = {
                "texts": ["Text 1", "Text 2"],
                "ids": ["id1", "id2"],
                "action": "add",
            }
            result = component.invoke(mock_message_fixture, data)

            # Verify the vector store's add_texts method was called
            component.vector_store.add_texts.assert_called_once_with(
                ["Text 1", "Text 2"],
                ids=["id1", "id2"],
            )

            # Verify the result
            assert result == {"result": "OK"}

    def test_invoke_add_data_with_single_id(self, mock_message_fixture):
        """Test invoke method with add action and single ID for multiple texts."""
        with patch.object(
            LangChainVectorStoreEmbeddingsBase, "__init__", return_value=None
        ) as mock_init:
            component = LangChainVectorStoreEmbeddingsIndex(config={})
            component.vector_store = MagicMock()

            # Call invoke with single ID for multiple texts
            data = {
                "texts": ["Text 1", "Text 2"],
                "ids": "common_id",
                "action": "add",
            }
            result = component.invoke(mock_message_fixture, data)

            # Verify the vector store's add_texts method was called
            component.vector_store.add_texts.assert_called_once_with(
                ["Text 1", "Text 2"],
                ids=["common_id", "common_id"],
            )

            # Verify the result
            assert result == {"result": "OK"}

    def test_invoke_delete_data(self, mock_message_fixture):
        """Test invoke method with delete action."""
        with patch.object(
            LangChainVectorStoreEmbeddingsBase, "__init__", return_value=None
        ) as mock_init:
            component = LangChainVectorStoreEmbeddingsIndex(config={})
            component.vector_store = MagicMock()

            # Call invoke with delete action
            data = {
                "ids": ["id1", "id2"],
                "texts": [
                    "Text 1",
                    "Text 2",
                ],  # texts are required by schema but not used for delete
                "action": "delete",
            }
            result = component.invoke(mock_message_fixture, data)

            # Verify the vector store's delete method was called
            component.vector_store.delete.assert_called_once_with(["id1", "id2"])

            # Verify the result
            assert result == {"result": "OK"}

    def test_invoke_delete_data_no_ids(self, mock_message_fixture):
        """Test invoke method with delete action but no IDs."""
        with patch.object(
            LangChainVectorStoreEmbeddingsBase, "__init__", return_value=None
        ) as mock_init:
            component = LangChainVectorStoreEmbeddingsIndex(config={})
            component.vector_store = MagicMock()

            # Call invoke with delete action but no IDs
            data = {
                "texts": ["Text 1", "Text 2"],
                "action": "delete",
            }

            # Verify that ValueError is raised
            with pytest.raises(ValueError) as excinfo:
                component.invoke(mock_message_fixture, data)

            assert "No IDs provided to delete" in str(excinfo.value)

            # Verify the vector store's delete method was not called
            component.vector_store.delete.assert_not_called()

    def test_invoke_invalid_action(self, mock_message_fixture):
        """Test invoke method with invalid action."""
        with patch.object(
            LangChainVectorStoreEmbeddingsBase, "__init__", return_value=None
        ) as mock_init:
            component = LangChainVectorStoreEmbeddingsIndex(config={})
            component.vector_store = MagicMock()

            # Call invoke with invalid action
            data = {
                "texts": ["Text 1", "Text 2"],
                "action": "invalid_action",
            }

            # Verify that ValueError is raised
            with pytest.raises(ValueError) as excinfo:
                component.invoke(mock_message_fixture, data)

            assert "Invalid action" in str(excinfo.value)

            # Verify the vector store's methods were not called
            component.vector_store.add_texts.assert_not_called()
            component.vector_store.delete.assert_not_called()
