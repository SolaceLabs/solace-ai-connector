"""Unit tests for LiteLLMChatModelWithHistory."""

import pytest
import time
from unittest.mock import patch, MagicMock, call, ANY

from solace_ai_connector.components.general.llm.litellm.litellm_chat_model_with_history import (
    LiteLLMChatModelWithHistory,
    info,
)
from solace_ai_connector.components.general.llm.litellm.litellm_chat_model_base import (
    LiteLLMChatModelBase,
)
from solace_ai_connector.components.general.llm.common.chat_history_handler import (
    ChatHistoryHandler,
)


class TestLiteLLMChatModelWithHistory:
    """Tests for the LiteLLMChatModelWithHistory class."""

    def test_info_dictionary(self):
        """Test that the info dictionary is properly defined."""
        # Verify the class name and description
        assert info["class_name"] == "LiteLLMChatModelWithHistory"
        assert (
            info["description"]
            == "LiteLLM model handler component with conversation history"
        )

        # Verify the additional config parameters
        config_param_names = [param["name"] for param in info["config_parameters"]]
        assert "history_max_turns" in config_param_names
        assert "history_max_time" in config_param_names

        # Verify the input schema includes clear_history_but_keep_depth
        assert "clear_history_but_keep_depth" in info["input_schema"]["properties"]

    @patch(
        "solace_ai_connector.components.general.llm.litellm.litellm_base.litellm.Router"
    )
    @patch.object(LiteLLMChatModelBase, "invoke")
    def test_invoke_without_session_id(self, mock_base_invoke, mock_router):
        """Test that invoke raises ValueError when session_id is not provided."""
        component = LiteLLMChatModelWithHistory(config={})

        with pytest.raises(ValueError) as excinfo:
            component.invoke(MagicMock(), {"messages": []})

        assert "session_id is not provided" in str(excinfo.value)
        mock_base_invoke.assert_not_called()

    @patch(
        "solace_ai_connector.components.general.llm.litellm.litellm_base.litellm.Router"
    )
    @patch.object(LiteLLMChatModelBase, "invoke")
    def test_invoke_with_new_session(
        self, mock_base_invoke, mock_router, mock_message_fixture
    ):
        """Test invoke with a new session."""
        component = LiteLLMChatModelWithHistory(
            flow_name="test_flow", config={"component_name": "test_component"}
        )

        # Mock kv_store methods
        mock_history = {}
        component.kv_store_get = MagicMock(return_value=mock_history)
        component.kv_store_set = MagicMock()
        component.get_lock = MagicMock()
        component.prune_history = MagicMock()

        # Mock base invoke to return a response
        mock_base_invoke.return_value = {"content": "Hello, I'm an AI"}

        # Call invoke with a session_id
        data = {
            "session_id": "test_session",
            "messages": [{"role": "user", "content": "Hello"}],
        }
        result = component.invoke(mock_message_fixture, data)

        # Verify the result
        assert result == {"content": "Hello, I'm an AI"}

        # Verify kv_store operations
        component.kv_store_get.assert_called_once_with(
            "test_flow_test_component_history"
        )

        # Verify the history was updated and stored
        expected_history = {
            "test_session": {
                "messages": [
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hello, I'm an AI"},
                ],
                "last_accessed": ANY,
            }
        }
        component.kv_store_set.assert_called_once()
        actual_history = component.kv_store_set.call_args[0][1]
        assert "test_session" in actual_history
        assert len(actual_history["test_session"]["messages"]) == 2
        assert actual_history["test_session"]["messages"][0] == {
            "role": "user",
            "content": "Hello",
        }
        assert actual_history["test_session"]["messages"][1] == {
            "role": "assistant",
            "content": "Hello, I'm an AI",
        }

        # Verify base invoke was called with the correct messages
        mock_base_invoke.assert_called_once()
        invoke_args = mock_base_invoke.call_args[0]
        assert invoke_args[0] == mock_message_fixture
        assert invoke_args[1]["messages"][0] == {"role": "user", "content": "Hello"}

    @patch(
        "solace_ai_connector.components.general.llm.litellm.litellm_base.litellm.Router"
    )
    @patch.object(LiteLLMChatModelBase, "invoke")
    def test_invoke_with_existing_session(
        self, mock_base_invoke, mock_router, mock_message_fixture
    ):
        """Test invoke with an existing session."""
        component = LiteLLMChatModelWithHistory(
            flow_name="test_flow", config={"component_name": "test_component"}
        )

        # Setup existing history
        existing_history = {
            "test_session": {
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant"},
                    {"role": "user", "content": "What's your name?"},
                    {"role": "assistant", "content": "I'm an AI assistant"},
                ],
                "last_accessed": time.time(),
            }
        }

        # Mock kv_store methods
        component.kv_store_get = MagicMock(return_value=existing_history)
        component.kv_store_set = MagicMock()
        component.get_lock = MagicMock()
        component.prune_history = MagicMock()

        # Mock base invoke to return a response
        mock_base_invoke.return_value = {"content": "I can help with that"}

        # Call invoke with a session_id and new message
        data = {
            "session_id": "test_session",
            "messages": [{"role": "user", "content": "Can you help me?"}],
        }
        result = component.invoke(mock_message_fixture, data)

        # Verify the result
        assert result == {"content": "I can help with that"}

        # Verify base invoke was called with all messages in history plus the new one
        mock_base_invoke.assert_called_once()
        invoke_args = mock_base_invoke.call_args[0]
        assert invoke_args[1]["messages"][0] == {
            "role": "system",
            "content": "You are a helpful assistant",
        }
        assert invoke_args[1]["messages"][1] == {
            "role": "user",
            "content": "What's your name?",
        }
        assert invoke_args[1]["messages"][2] == {
            "role": "assistant",
            "content": "I'm an AI assistant",
        }
        assert invoke_args[1]["messages"][3] == {
            "role": "user",
            "content": "Can you help me?",
        }

        # Verify the history was updated with both the new message and the response
        component.kv_store_set.assert_called_once()
        actual_history = component.kv_store_set.call_args[0][1]
        assert (
            len(actual_history["test_session"]["messages"]) == 5
        )  # system + 2 turns + new message + response
        assert actual_history["test_session"]["messages"][-1] == {
            "role": "assistant",
            "content": "I can help with that",
        }

    @patch(
        "solace_ai_connector.components.general.llm.litellm.litellm_base.litellm.Router"
    )
    @patch.object(LiteLLMChatModelBase, "invoke")
    def test_system_message_replacement(
        self, mock_base_invoke, mock_router, mock_message_fixture
    ):
        """Test that a new system message replaces the existing one."""
        component = LiteLLMChatModelWithHistory(
            flow_name="test_flow", config={"component_name": "test_component"}
        )

        # Setup existing history with a system message
        existing_history = {
            "test_session": {
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant"},
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi there"},
                ],
                "last_accessed": time.time(),
            }
        }

        # Mock kv_store methods
        component.kv_store_get = MagicMock(return_value=existing_history)
        component.kv_store_set = MagicMock()
        component.get_lock = MagicMock()
        component.prune_history = MagicMock()

        # Mock base invoke to return a response
        mock_base_invoke.return_value = {"content": "I'll be more creative"}

        # Call invoke with a new system message
        data = {
            "session_id": "test_session",
            "messages": [
                {"role": "system", "content": "You are a creative assistant"},
                {"role": "user", "content": "Tell me a story"},
            ],
        }
        result = component.invoke(mock_message_fixture, data)

        # Verify the result
        assert result == {"content": "I'll be more creative"}

        # Verify base invoke was called with the updated system message
        mock_base_invoke.assert_called_once()
        invoke_args = mock_base_invoke.call_args[0]
        assert invoke_args[1]["messages"][0] == {
            "role": "system",
            "content": "You are a creative assistant",
        }
        assert invoke_args[1]["messages"][1] == {
            "role": "user",
            "content": "Hello",
        }
        assert invoke_args[1]["messages"][2] == {
            "role": "assistant",
            "content": "Hi there",
        }
        assert invoke_args[1]["messages"][3] == {
            "role": "user",
            "content": "Tell me a story",
        }

        # Verify the history was updated correctly
        component.kv_store_set.assert_called_once()
        actual_history = component.kv_store_set.call_args[0][1]
        assert actual_history["test_session"]["messages"][0] == {
            "role": "system",
            "content": "You are a creative assistant",
        }

    @patch(
        "solace_ai_connector.components.general.llm.litellm.litellm_base.litellm.Router"
    )
    @patch.object(LiteLLMChatModelBase, "invoke")
    def test_clear_history_but_keep_depth(
        self, mock_base_invoke, mock_router, mock_message_fixture
    ):
        """Test the clear_history_but_keep_depth functionality."""
        component = LiteLLMChatModelWithHistory(
            flow_name="test_flow", config={"component_name": "test_component"}
        )

        # Setup existing history
        existing_history = {
            "test_session": {
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant"},
                    {"role": "user", "content": "Message 1"},
                    {"role": "assistant", "content": "Response 1"},
                    {"role": "user", "content": "Message 2"},
                    {"role": "assistant", "content": "Response 2"},
                    {"role": "user", "content": "Message 3"},
                    {"role": "assistant", "content": "Response 3"},
                ],
                "last_accessed": time.time(),
            }
        }

        # Mock methods
        component.kv_store_get = MagicMock(return_value=existing_history)
        component.kv_store_set = MagicMock()
        component.get_lock = MagicMock()
        component.clear_history_but_keep_depth = MagicMock()

        # Mock base invoke to return a response
        mock_base_invoke.return_value = {"content": "New response"}

        # Call invoke with clear_history_but_keep_depth=2
        data = {
            "session_id": "test_session",
            "messages": [{"role": "user", "content": "New message"}],
            "clear_history_but_keep_depth": 2,
        }
        component.invoke(mock_message_fixture, data)

        # Verify clear_history_but_keep_depth was called with correct parameters
        component.clear_history_but_keep_depth.assert_called_once_with(
            "test_session", 2, existing_history
        )
