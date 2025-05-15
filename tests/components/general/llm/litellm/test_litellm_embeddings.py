"""Unit tests for LiteLLMEmbeddings."""

import pytest
from unittest.mock import patch, MagicMock

from solace_ai_connector.components.general.llm.litellm.litellm_embeddings import (
    LiteLLMEmbeddings,
    info,
)
from solace_ai_connector.components.general.llm.litellm.litellm_base import (
    LiteLLMBase,
    litellm_info_base,
)


class TestLiteLLMEmbeddings:
    """Tests for the LiteLLMEmbeddings class."""

    @patch(
        "solace_ai_connector.components.general.llm.litellm.litellm_base.litellm.Router"
    )
    def test_initialization(self, mock_router, valid_load_balancer_config):
        """Test that LiteLLMEmbeddings initializes correctly."""
        config = {"load_balancer": valid_load_balancer_config}
        component = LiteLLMEmbeddings(config=config)

        # Verify it's an instance of the base class
        assert isinstance(component, LiteLLMBase)

        # Verify the info dictionary was passed correctly
        assert component.module_info["class_name"] == "LiteLLMEmbeddings"
        assert (
            component.module_info["description"] == "Embed text using a LiteLLM model"
        )

    def test_info_dictionary(self):
        """Test that the info dictionary is properly defined."""
        # Verify the info dictionary is based on the base class's info
        assert info["class_name"] == "LiteLLMEmbeddings"
        assert info["description"] == "Embed text using a LiteLLM model"

        # Verify it contains all the necessary keys
        assert "input_schema" in info
        assert "output_schema" in info
        assert "config_parameters" in info

        # Verify the input schema has the required properties
        assert "items" in info["input_schema"]["properties"]
        assert info["input_schema"]["required"] == ["items"]

        # Verify the output schema has the required properties
        assert "embeddings" in info["output_schema"]["properties"]
        assert info["output_schema"]["required"] == ["embeddings"]

    @patch(
        "solace_ai_connector.components.general.llm.litellm.litellm_base.litellm.Router"
    )
    def test_invoke_with_single_item(
        self, mock_router, mock_message_fixture, valid_load_balancer_config
    ):
        """Test invoke method with a single item."""
        # Setup mock response
        mock_router_instance = mock_router.return_value
        mock_router_instance.embedding.return_value = {
            "data": [{"embedding": [0.1, 0.2, 0.3]}]
        }

        # Create component with proper configuration
        component = LiteLLMEmbeddings(
            config={"component_config": {"load_balancer": valid_load_balancer_config}}
        )

        # Mock the router property directly to ensure it's properly set
        component.router = mock_router_instance

        # Call invoke with a single item
        data = {"items": "This is a test sentence"}
        result = component.invoke(mock_message_fixture, data)

        # Verify the result
        assert result == {"embeddings": [[0.1, 0.2, 0.3]]}

        # Verify router.embedding was called with the correct parameters
        mock_router_instance.embedding.assert_called_once_with(
            model=valid_load_balancer_config[0]["model_name"],
            input="This is a test sentence",
        )

    @patch(
        "solace_ai_connector.components.general.llm.litellm.litellm_base.litellm.Router"
    )
    def test_invoke_with_multiple_items(
        self, mock_router, mock_message_fixture, valid_load_balancer_config
    ):
        """Test invoke method with multiple items."""
        # Setup mock response
        mock_router_instance = mock_router.return_value
        mock_router_instance.embedding.return_value = {
            "data": [{"embedding": [0.1, 0.2, 0.3]}, {"embedding": [0.4, 0.5, 0.6]}]
        }

        # Create component with proper configuration
        component = LiteLLMEmbeddings(
            config={"component_config": {"load_balancer": valid_load_balancer_config}}
        )

        # Mock the router property directly to ensure it's properly set
        component.router = mock_router_instance

        # Call invoke with multiple items
        data = {"items": ["First sentence", "Second sentence"]}
        result = component.invoke(mock_message_fixture, data)

        # Verify the result
        assert result == {"embeddings": [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]}

        # Verify router.embedding was called with the correct parameters
        mock_router_instance.embedding.assert_called_once_with(
            model=valid_load_balancer_config[0]["model_name"],
            input=["First sentence", "Second sentence"],
        )

    @patch(
        "solace_ai_connector.components.general.llm.litellm.litellm_base.litellm.Router"
    )
    def test_invoke_with_empty_response(
        self, mock_router, mock_message_fixture, valid_load_balancer_config
    ):
        """Test invoke method with an empty response."""
        # Setup mock response
        mock_router_instance = mock_router.return_value
        mock_router_instance.embedding.return_value = {"data": []}

        # Create component with proper configuration
        component = LiteLLMEmbeddings(
            config={"component_config": {"load_balancer": valid_load_balancer_config}}
        )

        # Mock the router property directly to ensure it's properly set
        component.router = mock_router_instance

        # Call invoke
        data = {"items": "This is a test sentence"}
        result = component.invoke(mock_message_fixture, data)

        # Verify the result
        assert result == {"embeddings": []}
