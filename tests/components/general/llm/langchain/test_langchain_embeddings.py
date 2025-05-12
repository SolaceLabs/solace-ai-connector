"""Unit tests for LangChainEmbeddings."""

import pytest
from unittest.mock import patch, MagicMock

from solace_ai_connector.components.general.llm.langchain.langchain_embeddings import (
    LangChainEmbeddings,
    info,
)
from solace_ai_connector.components.general.llm.langchain.langchain_base import (
    LangChainBase,
)


class TestLangChainEmbeddings:
    """Tests for the LangChainEmbeddings class."""

    def test_initialization(self):
        """Test that LangChainEmbeddings initializes correctly."""
        with patch.object(LangChainBase, "__init__", return_value=None) as mock_init:
            # Initialize the component
            component = LangChainEmbeddings(config={})

            # Verify it's an instance of the base class
            assert isinstance(component, LangChainBase)

            # Verify __init__ was called with the correct parameters
            mock_init.assert_called_once_with(info, config={})

    def test_info_dictionary(self):
        """Test that the info dictionary is properly defined."""
        # Verify the class name and description
        assert info["class_name"] == "LangChainEmbeddings"
        assert "embeddings" in info["description"].lower()

        # Verify it contains all the necessary keys
        assert "input_schema" in info
        assert "output_schema" in info
        assert "config_parameters" in info

        # Verify the input schema has the required properties
        assert "items" in info["input_schema"]["properties"]
        assert "type" in info["input_schema"]["properties"]
        assert info["input_schema"]["required"] == ["items"]

        # Verify the output schema has the required properties
        assert "embedding" in info["output_schema"]["properties"]
        assert info["output_schema"]["required"] == ["embedding"]

    def test_invoke_with_single_document(
        self, mock_message_fixture, mock_embedding_component
    ):
        """Test invoke method with a single document."""
        with patch.object(LangChainBase, "__init__", return_value=None) as mock_init:
            component = LangChainEmbeddings(config={})
            component.component = mock_embedding_component

            # Call invoke with a single document
            data = {"items": "This is a test sentence"}
            result = component.invoke(mock_message_fixture, data)

            # Verify the component's embed_documents method was called
            mock_embedding_component.embed_documents.assert_called_once_with(
                ["This is a test sentence"]
            )

            # Verify the result
            assert result == {"embeddings": [[0.1, 0.2, 0.3]]}

    def test_invoke_with_multiple_documents(
        self, mock_message_fixture, mock_embedding_component
    ):
        """Test invoke method with multiple documents."""
        with patch.object(LangChainBase, "__init__", return_value=None) as mock_init:
            component = LangChainEmbeddings(config={})
            component.component = mock_embedding_component

            # Call invoke with multiple documents
            data = {"items": ["First sentence", "Second sentence"]}
            result = component.invoke(mock_message_fixture, data)

            # Verify the component's embed_documents method was called
            mock_embedding_component.embed_documents.assert_called_once_with(
                ["First sentence", "Second sentence"]
            )

            # Verify the result
            assert result == {"embeddings": [[0.1, 0.2, 0.3]]}

    def test_invoke_with_query_type(
        self, mock_message_fixture, mock_embedding_component
    ):
        """Test invoke method with query type."""
        with patch.object(LangChainBase, "__init__", return_value=None) as mock_init:
            component = LangChainEmbeddings(config={})
            component.component = mock_embedding_component

            # Call invoke with query type
            data = {"items": "This is a query", "type": "query"}
            result = component.invoke(mock_message_fixture, data)

            # Verify the component's embed_query method was called
            mock_embedding_component.embed_query.assert_called_once_with(
                "This is a query"
            )

            # Verify the result
            assert result == {"embeddings": [[0.1, 0.2, 0.3]]}

    def test_invoke_with_multiple_queries(
        self, mock_message_fixture, mock_embedding_component
    ):
        """Test invoke method with multiple queries."""
        with patch.object(LangChainBase, "__init__", return_value=None) as mock_init:
            component = LangChainEmbeddings(config={})
            component.component = mock_embedding_component

            # Call invoke with multiple queries
            data = {"items": ["First query", "Second query"], "type": "query"}
            result = component.invoke(mock_message_fixture, data)

            # Verify the component's embed_query method was called for each query
            assert mock_embedding_component.embed_query.call_count == 2
            mock_embedding_component.embed_query.assert_any_call("First query")
            mock_embedding_component.embed_query.assert_any_call("Second query")

            # Verify the result
            assert result == {"embeddings": [[0.1, 0.2, 0.3], [0.1, 0.2, 0.3]]}

    def test_invoke_with_image_type(
        self, mock_message_fixture, mock_embedding_component
    ):
        """Test invoke method with image type."""
        with patch.object(LangChainBase, "__init__", return_value=None) as mock_init:
            component = LangChainEmbeddings(config={})
            component.component = mock_embedding_component

            # Call invoke with image type
            data = {"items": "path/to/image.jpg", "type": "image"}
            result = component.invoke(mock_message_fixture, data)

            # Verify the component's embed_images method was called
            mock_embedding_component.embed_images.assert_called_once_with(
                ["path/to/image.jpg"]
            )

            # Verify the result
            assert result == {"embeddings": [[0.1, 0.2, 0.3]]}

    def test_embed_documents(self, mock_embedding_component):
        """Test embed_documents method."""
        with patch.object(LangChainBase, "__init__", return_value=None) as mock_init:
            component = LangChainEmbeddings(config={})
            component.component = mock_embedding_component

            # Call embed_documents
            result = component.embed_documents(["Document 1", "Document 2"])

            # Verify the component's embed_documents method was called
            mock_embedding_component.embed_documents.assert_called_once_with(
                ["Document 1", "Document 2"]
            )

            # Verify the result
            assert result == {"embeddings": [[0.1, 0.2, 0.3]]}

    def test_embed_queries(self, mock_embedding_component):
        """Test embed_queries method."""
        with patch.object(LangChainBase, "__init__", return_value=None) as mock_init:
            component = LangChainEmbeddings(config={})
            component.component = mock_embedding_component

            # Call embed_queries
            result = component.embed_queries(["Query 1", "Query 2"])

            # Verify the component's embed_query method was called for each query
            assert mock_embedding_component.embed_query.call_count == 2
            mock_embedding_component.embed_query.assert_any_call("Query 1")
            mock_embedding_component.embed_query.assert_any_call("Query 2")

            # Verify the result
            assert result == {"embeddings": [[0.1, 0.2, 0.3], [0.1, 0.2, 0.3]]}

    def test_embed_images(self, mock_embedding_component):
        """Test embed_images method."""
        with patch.object(LangChainBase, "__init__", return_value=None) as mock_init:
            component = LangChainEmbeddings(config={})
            component.component = mock_embedding_component

            # Call embed_images
            result = component.embed_images(["image1.jpg", "image2.jpg"])

            # Verify the component's embed_images method was called
            mock_embedding_component.embed_images.assert_called_once_with(
                ["image1.jpg", "image2.jpg"]
            )

            # Verify the result
            assert result == {"embeddings": [[0.1, 0.2, 0.3]]}
