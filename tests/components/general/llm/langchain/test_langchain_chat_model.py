"""Unit tests for LangChainChatModel."""

import pytest
from unittest.mock import patch, MagicMock
from collections import namedtuple

from solace_ai_connector.components.general.llm.langchain.langchain_chat_model import (
    LangChainChatModel,
    info,
)
from solace_ai_connector.components.general.llm.langchain.langchain_chat_model_base import (
    LangChainChatModelBase,
    info_base,
)


class TestLangChainChatModel:
    """Tests for the LangChainChatModel class."""

    def test_initialization(self):
        """Test that LangChainChatModel initializes correctly."""
        with patch.object(
            LangChainChatModelBase, "__init__", return_value=None
        ) as mock_init:
            # Initialize the component
            component = LangChainChatModel(config={})

            # Verify it's an instance of the base class
            assert isinstance(component, LangChainChatModelBase)

            # Verify __init__ was called with the correct parameters
            mock_init.assert_called_once_with(info, config={})

    def test_info_dictionary(self):
        """Test that the info dictionary is properly defined."""
        # Verify the info dictionary is based on the base class's info
        assert info["class_name"] == "LangChainChatModel"

        # Verify it contains all the necessary keys from the base class
        assert "input_schema" in info
        assert "output_schema" in info
        assert "config_parameters" in info

        # Verify the input schema is the same as the base class
        assert info["input_schema"] == info_base["input_schema"]

        # Verify the output schema is the same as the base class
        assert info["output_schema"] == info_base["output_schema"]

    def test_invoke_model_streaming(self, mock_message_fixture):
        """Test invoke_model method in streaming mode."""
        with patch.object(
            LangChainChatModelBase, "__init__", return_value=None
        ) as mock_init:
            component = LangChainChatModel(config={})
            component.component = MagicMock()
            component.stream_batch_size = 2
            component.stream_to_flow = "test_flow"
            component.send_streaming_message = MagicMock()

            # Mock the streaming response
            chunk1 = MagicMock()
            chunk1.content = "Hello"
            chunk2 = MagicMock()
            chunk2.content = " world"
            component.component.stream.return_value = [chunk1, chunk2]

            # Set a larger batch size to ensure only one batch is sent during the loop
            component.stream_batch_size = 20

            # Call invoke_model with streaming=True
            messages = [{"role": "user", "content": "Hello"}]
            result = component.invoke_model(mock_message_fixture, messages, stream=True)

            # Verify the component's stream method was called
            component.component.stream.assert_called_once_with(messages)

            # Verify the result
            assert result.content == "Hello world"

            # Verify send_streaming_message was called once at the end of the loop
            # With our batch size of 20 and total content of "Hello world" (11 chars),
            # it won't trigger a send during the loop, only at the end
            assert component.send_streaming_message.call_count == 1
            # The call should have first_chunk=True (since no previous chunks were sent) and last_chunk=True
            assert (
                component.send_streaming_message.call_args_list[0][0][3] is not None
            )  # response_uuid
            assert (
                component.send_streaming_message.call_args_list[0][0][4] is True
            )  # first_chunk
            assert (
                component.send_streaming_message.call_args_list[0][0][5] is True
            )  # last_chunk

    def test_invoke_model_streaming_no_flow(self, mock_message_fixture):
        """Test invoke_model method in streaming mode with no flow specified."""
        with patch.object(
            LangChainChatModelBase, "__init__", return_value=None
        ) as mock_init:
            component = LangChainChatModel(config={})
            component.component = MagicMock()
            component.stream_batch_size = 2
            component.stream_to_flow = ""  # No flow specified
            component.send_streaming_message = MagicMock()

            # Mock the streaming response
            chunk1 = MagicMock()
            chunk1.content = "Hello"
            chunk2 = MagicMock()
            chunk2.content = " world"
            component.component.stream.return_value = [chunk1, chunk2]

            # Call invoke_model with streaming=True
            messages = [{"role": "user", "content": "Hello"}]
            result = component.invoke_model(mock_message_fixture, messages, stream=True)

            # Verify the component's stream method was called
            component.component.stream.assert_called_once_with(messages)

            # Verify the result
            assert result.content == "Hello world"

            # Verify send_streaming_message was not called
            component.send_streaming_message.assert_not_called()
