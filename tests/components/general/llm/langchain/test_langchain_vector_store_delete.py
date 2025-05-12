"""Unit tests for LangChainVectorStoreDelete."""

import pytest
from unittest.mock import patch, MagicMock

from solace_ai_connector.components.general.llm.langchain.langchain_vector_store_delete import (
    LangChainVectorStoreDelete,
    info,
)
from solace_ai_connector.components.general.llm.langchain.langchain_vector_store_embedding_base import (
    LangChainVectorStoreEmbeddingsBase,
)


class TestLangChainVectorStoreDelete:
    """Tests for the LangChainVectorStoreDelete class."""

    def test_initialization(self):
        """Test that LangChainVectorStoreDelete initializes correctly."""
        with patch.object(
            LangChainVectorStoreEmbeddingsBase, "__init__", return_value=None
        ) as mock_init:
            # Initialize the component
            component = LangChainVectorStoreDelete(config={})

            # Verify it's an instance of the base class
            assert isinstance(component, LangChainVectorStoreEmbeddingsBase)

            # Verify __init__ was called with the correct parameters
            mock_init.assert_called_once_with(info, config={})

    def test_info_dictionary(self):
        """Test that the info dictionary is properly defined."""
        # Verify the class name and description
        assert info["class_name"] == "LangChainVectorStoreDelete"
        assert "delete" in info["description"].lower()

        # Verify it contains all the necessary keys
        assert "input_schema" in info
        assert "output_schema" in info
        assert "config_parameters" in info

        # Verify the config parameters include delete_ids and delete_kwargs
        config_param_names = [param["name"] for param in info["config_parameters"]]
        assert "delete_ids" in config_param_names
        assert "delete_kwargs" in config_param_names

    def test_invoke_with_delete_ids(self, mock_message_fixture):
        """Test invoke method with delete_ids."""
        with patch.object(
            LangChainVectorStoreEmbeddingsBase, "__init__", return_value=None
        ) as mock_init:
            component = LangChainVectorStoreDelete(config={})
            component.vector_store = MagicMock()
            component.vector_store_info = {"name": "TestVectorStore"}

            # Mock get_config to return delete_ids and delete_kwargs
            component.get_config = MagicMock(
                side_effect=lambda key, default=None: ["id1", "id2"]
                if key == "delete_ids"
                else {"param1": "value1"}
                if key == "delete_kwargs"
                else default
            )

            # Mock resolve_callable_config to return the same kwargs
            component.resolve_callable_config = MagicMock(
                return_value={"param1": "value1"}
            )

            # Call invoke
            result = component.invoke(mock_message_fixture, {})

            # Verify the vector store's delete method was called
            component.vector_store.delete.assert_called_once_with(
                ["id1", "id2"], param1="value1"
            )

            # Verify the result
            assert result == {"result": component.vector_store.delete.return_value}

    def test_invoke_with_milvus_expr(self, mock_message_fixture):
        """Test invoke method with Milvus vector store and expr."""
        with patch.object(
            LangChainVectorStoreEmbeddingsBase, "__init__", return_value=None
        ) as mock_init:
            component = LangChainVectorStoreDelete(config={})
            component.vector_store = MagicMock()
            component.vector_store_info = {"name": "Milvus"}

            # Mock get_config to return delete_kwargs with expr
            component.get_config = MagicMock(
                side_effect=lambda key, default=None: None
                if key == "delete_ids"
                else {"expr": "field == 'value'"}
                if key == "delete_kwargs"
                else default
            )

            # Mock resolve_callable_config to return the same kwargs
            component.resolve_callable_config = MagicMock(
                return_value={"expr": "field == 'value'"}
            )

            # Mock get_pks to return IDs
            component.vector_store.get_pks = MagicMock(return_value=["id1", "id2"])

            # Call invoke
            result = component.invoke(mock_message_fixture, {})

            # Verify get_pks was called with the expr
            component.vector_store.get_pks.assert_called_once_with("field == 'value'")

            # Verify the vector store's delete method was called with the IDs from get_pks
            component.vector_store.delete.assert_called_once_with(["id1", "id2"])

            # Verify the result
            assert result == {"result": component.vector_store.delete.return_value}

    def test_invoke_with_milvus_no_expr(self, mock_message_fixture):
        """Test invoke method with Milvus vector store but no expr."""
        with patch.object(
            LangChainVectorStoreEmbeddingsBase, "__init__", return_value=None
        ) as mock_init:
            component = LangChainVectorStoreDelete(config={})
            component.vector_store = MagicMock()
            component.vector_store_info = {"name": "Milvus"}

            # Mock get_config to return delete_kwargs without expr
            component.get_config = MagicMock(
                side_effect=lambda key, default=None: None
                if key == "delete_ids"
                else {"param1": "value1"}
                if key == "delete_kwargs"
                else default
            )

            # Mock resolve_callable_config to return the same kwargs
            component.resolve_callable_config = MagicMock(
                return_value={"param1": "value1"}
            )

            # Verify that ValueError is raised
            with pytest.raises(ValueError) as excinfo:
                component.invoke(mock_message_fixture, {})

            assert "expr not provided in delete_kwargs" in str(excinfo.value)
