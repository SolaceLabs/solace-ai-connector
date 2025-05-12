"""Unit tests for LiteLLMChatModel."""

import pytest
from unittest.mock import patch, MagicMock

from solace_ai_connector.components.general.llm.litellm.litellm_chat_model import (
    LiteLLMChatModel,
    info,
)
from solace_ai_connector.components.general.llm.litellm.litellm_chat_model_base import (
    LiteLLMChatModelBase,
    litellm_chat_info_base,
)


class TestLiteLLMChatModel:
    """Tests for the LiteLLMChatModel class."""

    @patch(
        "solace_ai_connector.components.general.llm.litellm.litellm_base.litellm.Router"
    )
    def test_initialization(self, mock_router, valid_load_balancer_config):
        """Test that LiteLLMChatModel initializes correctly."""
        config = {"load_balancer": valid_load_balancer_config}
        component = LiteLLMChatModel(config=config)

        # Verify it's an instance of the base class
        assert isinstance(component, LiteLLMChatModelBase)

        # Verify the info dictionary was passed correctly
        assert component.module_info["class_name"] == "LiteLLMChatModel"
        assert component.module_info["description"] == "LiteLLM chat component"

        # Verify it inherits the base class's functionality
        assert component.stream_to_flow == ""
        assert component.stream_to_next_component is False
        assert component.llm_mode == "none"
        assert component.stream_batch_size == 15

    def test_info_dictionary(self):
        """Test that the info dictionary is properly defined."""
        # Verify the info dictionary is based on the base class's info
        assert info["class_name"] == "LiteLLMChatModel"
        assert info["description"] == "LiteLLM chat component"

        # Verify it contains all the necessary keys from the base class
        assert "input_schema" in info
        assert "output_schema" in info
        assert "config_parameters" in info

        # Verify the input schema is the same as the base class
        assert info["input_schema"] == litellm_chat_info_base["input_schema"]

        # Verify the output schema is the same as the base class
        assert info["output_schema"] == litellm_chat_info_base["output_schema"]

    @patch.object(LiteLLMChatModelBase, "invoke")
    @patch(
        "solace_ai_connector.components.general.llm.litellm.litellm_base.litellm.Router"
    )
    def test_invoke_method_inheritance(
        self, mock_router, mock_invoke, mock_message_fixture, valid_load_balancer_config
    ):
        """Test that the invoke method is inherited from the base class."""
        config = {"load_balancer": valid_load_balancer_config}
        component = LiteLLMChatModel(config=config)

        data = {"messages": [{"role": "user", "content": "Hello"}]}
        component.invoke(mock_message_fixture, data)

        # Verify the base class's invoke method was called
        mock_invoke.assert_called_once_with(mock_message_fixture, data)
