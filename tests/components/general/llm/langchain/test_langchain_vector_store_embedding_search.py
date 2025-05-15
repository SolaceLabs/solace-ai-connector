"""Unit tests for LangChainVectorStoreEmbeddingsSearch."""

import pytest
from unittest.mock import patch, MagicMock

from solace_ai_connector.components.general.llm.langchain.langchain_vector_store_embedding_search import (
    LangChainVectorStoreEmbeddingsSearch,
    info,
)
from solace_ai_connector.components.general.llm.langchain.langchain_vector_store_embedding_base import (
    LangChainVectorStoreEmbeddingsBase,
)


class TestLangChainVectorStoreEmbeddingsSearch:
    """Tests for the LangChainVectorStoreEmbeddingsSearch class."""

    def test_initialization(self):
        """Test that LangChainVectorStoreEmbeddingsSearch initializes correctly."""
        with patch.object(
            LangChainVectorStoreEmbeddingsBase, "__init__", return_value=None
        ) as mock_init:
            # Initialize the component
            component = LangChainVectorStoreEmbeddingsSearch(config={})

            # Verify it's an instance of the base class
            assert isinstance(component, LangChainVectorStoreEmbeddingsBase)

            # Verify __init__ was called with the correct parameters
            mock_init.assert_called_once_with(info, config={})

    def test_info_dictionary(self):
        """Test that the info dictionary is properly defined."""
        # Verify the class name and description
        assert info["class_name"] == "LangChainVectorStoreEmbeddingsSearch"
        assert "search" in info["description"].lower()

        # Verify it contains all the necessary keys
        assert "input_schema" in info
        assert "output_schema" in info
        assert "config_parameters" in info

        # Verify the input schema has the required properties
        assert "text" in info["input_schema"]["properties"]
        assert info["input_schema"]["required"] == ["text"]

        # Verify the output schema is an array
        assert info["output_schema"]["type"] == "array"

    def test_invoke_success(self, mock_message_fixture, mock_vector_store):
        """Test successful invocation of the component."""
        with patch.object(
            LangChainVectorStoreEmbeddingsBase, "__init__", return_value=None
        ) as mock_init:
            # Create a component with mocked vector store
            component = LangChainVectorStoreEmbeddingsSearch(config={})
            component.vector_store = mock_vector_store
            component.get_config = MagicMock(
                side_effect=lambda key, default=None: 3
                if key == "max_results"
                else default
            )

            # Create a mock document with page_content and metadata
            mock_doc = MagicMock()
            mock_doc.page_content = "Test content"
            mock_doc.metadata = {"source": "test_source"}
            mock_vector_store.similarity_search.return_value = [mock_doc]

            # Call invoke
            data = {"text": "test query"}
            result = component.invoke(mock_message_fixture, data)

            # Verify the vector store's similarity_search method was called
            mock_vector_store.similarity_search.assert_called_once_with(
                "test query", k=3
            )

            # Verify the result
            assert result == {
                "result": [
                    {"text": "Test content", "metadata": {"source": "test_source"}}
                ]
            }

    def test_combine_context_from_same_source(self):
        """Test the combine_context method."""
        with patch.object(
            LangChainVectorStoreEmbeddingsBase, "__init__", return_value=None
        ) as mock_init:
            # Create a component
            component = LangChainVectorStoreEmbeddingsSearch(config={})

            # Create test results with the same source
            results = [
                {
                    "text": "Text 1",
                    "metadata": {"source_link": "source1", "key1": "value1"},
                },
                {
                    "text": "Text 2",
                    "metadata": {"source_link": "source1", "key2": "value2"},
                },
                {
                    "text": "Text 3",
                    "metadata": {"source_link": "source2", "key3": "value3"},
                },
            ]

            # Call combine_context
            combined = component.combine_context(results)

            # Verify the result
            assert len(combined) == 2  # Two unique sources

            # Find the combined source1 entry
            source1_entry = next(
                (
                    item
                    for item in combined
                    if item["metadata"].get("source_link") == "source1"
                ),
                None,
            )
            assert source1_entry is not None
            assert source1_entry["text"] == "Text 1 Text 2"
            assert source1_entry["metadata"]["key1"] == "value1"
            assert source1_entry["metadata"]["key2"] == "value2"

            # Find the source2 entry (should be unchanged)
            source2_entry = next(
                (
                    item
                    for item in combined
                    if item["metadata"].get("source_link") == "source2"
                ),
                None,
            )
            assert source2_entry is not None
            assert source2_entry["text"] == "Text 3"
            assert source2_entry["metadata"]["key3"] == "value3"

    def test_invoke_with_combine_context_true(
        self, mock_message_fixture, mock_vector_store
    ):
        """Test invoke with combine_context_from_same_source=True."""
        with patch.object(
            LangChainVectorStoreEmbeddingsBase, "__init__", return_value=None
        ) as mock_init:
            # Create a component with mocked vector store
            component = LangChainVectorStoreEmbeddingsSearch(config={})
            component.vector_store = mock_vector_store

            # Mock get_config to return max_results=3 and combine_context_from_same_source=True
            component.get_config = MagicMock(
                side_effect=lambda key, default=None: 3
                if key == "max_results"
                else True
                if key == "combine_context_from_same_source"
                else default
            )

            # Create mock documents with the same source
            mock_doc1 = MagicMock()
            mock_doc1.page_content = "Text 1"
            mock_doc1.metadata = {"source": "source1"}

            mock_doc2 = MagicMock()
            mock_doc2.page_content = "Text 2"
            mock_doc2.metadata = {"source": "source1"}

            mock_vector_store.similarity_search.return_value = [mock_doc1, mock_doc2]

            # Mock combine_context to return a combined result
            with patch.object(component, "combine_context") as mock_combine_context:
                mock_combine_context.return_value = [
                    {"text": "Text 1 Text 2", "metadata": {"source": "source1"}}
                ]

                # Call invoke
                data = {"text": "test query"}
                result = component.invoke(mock_message_fixture, data)

                # Verify combine_context was called
                mock_combine_context.assert_called_once()

                # Verify the result
                assert result == {
                    "result": [
                        {"text": "Text 1 Text 2", "metadata": {"source": "source1"}}
                    ]
                }

    def test_invoke_with_combine_context_false(
        self, mock_message_fixture, mock_vector_store
    ):
        """Test invoke with combine_context_from_same_source=False."""
        with patch.object(
            LangChainVectorStoreEmbeddingsBase, "__init__", return_value=None
        ) as mock_init:
            # Create a component with mocked vector store
            component = LangChainVectorStoreEmbeddingsSearch(config={})
            component.vector_store = mock_vector_store

            # Mock get_config to return max_results=3 and combine_context_from_same_source=False
            component.get_config = MagicMock(
                side_effect=lambda key, default=None: 3
                if key == "max_results"
                else False
                if key == "combine_context_from_same_source"
                else default
            )

            # Create mock documents with the same source
            mock_doc1 = MagicMock()
            mock_doc1.page_content = "Text 1"
            mock_doc1.metadata = {"source": "source1"}

            mock_doc2 = MagicMock()
            mock_doc2.page_content = "Text 2"
            mock_doc2.metadata = {"source": "source1"}

            mock_vector_store.similarity_search.return_value = [mock_doc1, mock_doc2]

            # Mock combine_context to ensure it's not called
            with patch.object(component, "combine_context") as mock_combine_context:
                # Call invoke
                data = {"text": "test query"}
                result = component.invoke(mock_message_fixture, data)

                # Verify combine_context was not called
                mock_combine_context.assert_not_called()

                # Verify the result contains both documents separately
                assert result == {
                    "result": [
                        {"text": "Text 1", "metadata": {"source": "source1"}},
                        {"text": "Text 2", "metadata": {"source": "source1"}},
                    ]
                }

    def test_metadata_pk_removal(self, mock_message_fixture, mock_vector_store):
        """Test that 'pk' field is removed from metadata."""
        with patch.object(
            LangChainVectorStoreEmbeddingsBase, "__init__", return_value=None
        ) as mock_init:
            # Create a component with mocked vector store
            component = LangChainVectorStoreEmbeddingsSearch(config={})
            component.vector_store = mock_vector_store
            component.get_config = MagicMock(
                side_effect=lambda key, default=None: 3
                if key == "max_results"
                else default
            )

            # Create a mock document with page_content and metadata including 'pk'
            mock_doc = MagicMock()
            mock_doc.page_content = "Test content"
            mock_doc.metadata = {"source": "test_source", "pk": "should_be_removed"}
            mock_vector_store.similarity_search.return_value = [mock_doc]

            # Call invoke
            data = {"text": "test query"}
            result = component.invoke(mock_message_fixture, data)

            # Verify the result doesn't contain 'pk' in metadata
            assert "pk" not in result["result"][0]["metadata"]
            assert result["result"][0]["metadata"]["source"] == "test_source"
