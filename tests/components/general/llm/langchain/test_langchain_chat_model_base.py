"""Unit tests for LangChainChatModelBase."""

import pytest
from unittest.mock import patch, MagicMock
from collections import namedtuple

# Mock the langchain imports
import sys
from unittest.mock import MagicMock


# Create mock classes for langchain message types
class HumanMessage(MagicMock):
    pass


class SystemMessage(MagicMock):
    pass


class AIMessage(MagicMock):
    pass


class FunctionMessage(MagicMock):
    pass


class ChatMessage(MagicMock):
    pass


# Mock the langchain module
mock_langchain = MagicMock()
mock_langchain.schema = MagicMock()
mock_langchain.schema.messages = MagicMock()
mock_langchain.schema.messages.HumanMessage = HumanMessage
mock_langchain.schema.messages.SystemMessage = SystemMessage
mock_langchain.schema.messages.AIMessage = AIMessage
mock_langchain.schema.messages.FunctionMessage = FunctionMessage
mock_langchain.schema.messages.ChatMessage = ChatMessage

# Mock langchain_core module
mock_langchain_core = MagicMock()
mock_langchain_core.output_parsers = MagicMock()
mock_langchain_core.output_parsers.JsonOutputParser = MagicMock()
mock_langchain_core.output_parsers.JsonOutputParser.invoke = MagicMock()

# Add the mocks to sys.modules
sys.modules["langchain"] = mock_langchain
sys.modules["langchain.schema"] = mock_langchain.schema
sys.modules["langchain.schema.messages"] = mock_langchain.schema.messages
sys.modules["langchain_core"] = mock_langchain_core
sys.modules["langchain_core.output_parsers"] = mock_langchain_core.output_parsers

from solace_ai_connector.components.general.llm.langchain.langchain_chat_model_base import (
    LangChainChatModelBase,
    info_base,
)


class TestLangChainChatModelBaseInitialization:
    """Tests for the __init__ method of LangChainChatModelBase."""

    def test_initialization_with_defaults(self):
        """Test initialization with default values."""
        with patch.object(
            LangChainChatModelBase, "load_component"
        ) as mock_load_component:
            with patch.object(
                LangChainChatModelBase, "create_component"
            ) as mock_create_component:
                with patch.object(
                    LangChainChatModelBase, "validate_config"
                ) as mock_validate_config:
                    # Mock the component class and instance
                    mock_component_class = MagicMock()
                    mock_component = MagicMock()
                    mock_load_component.return_value = mock_component_class
                    mock_create_component.return_value = mock_component
                    mock_validate_config.return_value = None

                    # Mock get_config to return expected values
                    with patch.object(
                        LangChainChatModelBase, "get_config"
                    ) as mock_get_config:

                        def side_effect(key, default=None):
                            if key == "llm_mode":
                                return "none"
                            elif key == "stream_to_flow":
                                return ""
                            elif key == "stream_batch_size":
                                return 15
                            elif key == "component_name":
                                return "test_component"
                            elif key == "component_config":
                                return {
                                    "langchain_module": "test_module",
                                    "langchain_class": "TestClass",
                                    "langchain_component_config": {},
                                }
                            elif key == "llm_response_format":
                                return "text"
                            return default

                        mock_get_config.side_effect = side_effect

                        # Initialize the component
                        component = LangChainChatModelBase(info=info_base, config={})

                    # Check default values
                    assert component.llm_mode == "none"
                    assert component.stream_to_flow == ""
                    assert component.stream_batch_size == 15

    def test_initialization_with_custom_config(self):
        """Test initialization with custom configuration."""
        with patch.object(
            LangChainChatModelBase, "load_component"
        ) as mock_load_component:
            with patch.object(
                LangChainChatModelBase, "create_component"
            ) as mock_create_component:
                with patch.object(
                    LangChainChatModelBase, "validate_config"
                ) as mock_validate_config:
                    # Mock the component class and instance
                    mock_component_class = MagicMock()
                    mock_component = MagicMock()
                    mock_load_component.return_value = mock_component_class
                    mock_create_component.return_value = mock_component
                    mock_validate_config.return_value = None

                    # Mock get_config to return expected values
                    with patch.object(
                        LangChainChatModelBase, "get_config"
                    ) as mock_get_config:

                        def side_effect(key, default=None):
                            if key == "llm_mode":
                                return "stream"
                            elif key == "stream_to_flow":
                                return "test_flow"
                            elif key == "stream_batch_size":
                                return 10
                            elif key == "component_name":
                                return "test_component"
                            elif key == "component_config":
                                return {
                                    "langchain_module": "test_module",
                                    "langchain_class": "TestClass",
                                    "langchain_component_config": {},
                                }
                            elif key == "llm_response_format":
                                return "text"
                            return default

                        mock_get_config.side_effect = side_effect

                        # Initialize the component
                        component = LangChainChatModelBase(info=info_base, config={})

                    # Check custom values
                    assert component.llm_mode == "stream"
                    assert component.stream_to_flow == "test_flow"
                    assert component.stream_batch_size == 10


class TestLangChainChatModelBaseInvoke:
    """Tests for the invoke method of LangChainChatModelBase."""

    def test_invalid_message_role(self, mock_message_fixture):
        """Test handling of invalid message roles."""
        with patch.object(
            LangChainChatModelBase, "load_component"
        ) as mock_load_component:
            with patch.object(
                LangChainChatModelBase, "create_component"
            ) as mock_create_component:
                with patch.object(
                    LangChainChatModelBase, "validate_config"
                ) as mock_validate_config:
                    # Mock the component class and instance
                    mock_component_class = MagicMock()
                    mock_component = MagicMock()
                    mock_load_component.return_value = mock_component_class
                    mock_create_component.return_value = mock_component
                    mock_validate_config.return_value = None

                    # Mock get_config to return expected values
                    with patch.object(
                        LangChainChatModelBase, "get_config"
                    ) as mock_get_config:

                        def side_effect(key, default=None):
                            if key == "llm_mode":
                                return "none"
                            elif key == "stream_to_flow":
                                return ""
                            elif key == "stream_batch_size":
                                return 15
                            elif key == "component_name":
                                return "test_component"
                            elif key == "component_config":
                                return {
                                    "langchain_module": "test_module",
                                    "langchain_class": "TestClass",
                                    "langchain_component_config": {},
                                }
                            elif key == "llm_response_format":
                                return "text"
                            return default

                        mock_get_config.side_effect = side_effect

                        # Initialize the component
                        component = LangChainChatModelBase(info=info_base, config={})

                    # Test with an invalid message role
                    data = {
                        "messages": [{"role": "invalid", "content": "Invalid role"}]
                    }
                    with pytest.raises(ValueError) as excinfo:
                        component.invoke(mock_message_fixture, data)

                    assert "Invalid message role" in str(excinfo.value)


class TestLangChainChatModelBaseResponseFormat:
    """Tests for the response format handling of LangChainChatModelBase."""

    def test_text_format_response(self, mock_message_fixture):
        """Test text format response."""
        with patch.object(
            LangChainChatModelBase, "load_component"
        ) as mock_load_component:
            with patch.object(
                LangChainChatModelBase, "create_component"
            ) as mock_create_component:
                with patch.object(
                    LangChainChatModelBase, "validate_config"
                ) as mock_validate_config:
                    # Mock the component class and instance
                    mock_component_class = MagicMock()
                    mock_component = MagicMock()
                    mock_load_component.return_value = mock_component_class
                    mock_create_component.return_value = mock_component
                    mock_validate_config.return_value = None

                    # Mock get_config to return expected values
                    with patch.object(
                        LangChainChatModelBase, "get_config"
                    ) as mock_get_config:

                        def side_effect(key, default=None):
                            if key == "llm_mode":
                                return "none"
                            elif key == "stream_to_flow":
                                return ""
                            elif key == "stream_batch_size":
                                return 15
                            elif key == "component_name":
                                return "test_component"
                            elif key == "component_config":
                                return {
                                    "langchain_module": "test_module",
                                    "langchain_class": "TestClass",
                                    "langchain_component_config": {},
                                }
                            elif key == "llm_response_format":
                                return "text"
                            return default

                        mock_get_config.side_effect = side_effect

                        # Initialize the component
                        component = LangChainChatModelBase(info=info_base, config={})

                        # Mock invoke_model to return a response
                        # This needs to be done AFTER component initialization
                        Result = namedtuple("Result", ["content", "response_uuid"])
                        component.invoke_model = MagicMock(
                            return_value=Result("Test response", "test-uuid")
                        )

                        # Test with a simple message
                        data = {"messages": [{"role": "user", "content": "Hello"}]}
                        result = component.invoke(mock_message_fixture, data)

                        # Check the result
                        assert result == "Test response"

    def test_json_format_response(self, mock_message_fixture):
        """Test JSON format response."""
        with patch.object(
            LangChainChatModelBase, "load_component"
        ) as mock_load_component:
            with patch.object(
                LangChainChatModelBase, "create_component"
            ) as mock_create_component:
                with patch.object(
                    LangChainChatModelBase, "validate_config"
                ) as mock_validate_config:
                    # Mock the component class and instance
                    mock_component_class = MagicMock()
                    mock_component = MagicMock()
                    mock_load_component.return_value = mock_component_class
                    mock_create_component.return_value = mock_component
                    mock_validate_config.return_value = None

                    # Mock get_config to return expected values
                    with patch.object(
                        LangChainChatModelBase, "get_config"
                    ) as mock_get_config:

                        def side_effect(key, default=None):
                            if key == "llm_mode":
                                return "none"
                            elif key == "stream_to_flow":
                                return ""
                            elif key == "stream_batch_size":
                                return 15
                            elif key == "component_name":
                                return "test_component"
                            elif key == "component_config":
                                return {
                                    "langchain_module": "test_module",
                                    "langchain_class": "TestClass",
                                    "langchain_component_config": {},
                                }
                            elif key == "llm_response_format":
                                return "json"
                            return default

                        mock_get_config.side_effect = side_effect

                        # Initialize the component
                        component = LangChainChatModelBase(info=info_base, config={})

                        # Mock invoke_model to return a response
                        # This needs to be done AFTER component initialization
                        Result = namedtuple("Result", ["content", "response_uuid"])
                        component.invoke_model = MagicMock(
                            return_value=Result('{"key": "value"}', "test-uuid")
                        )

                        # Mock JSON parser
                        # We need to patch at the module level where it's imported
                        with patch(
                            "solace_ai_connector.components.general.llm.langchain.langchain_chat_model_base.JsonOutputParser"
                        ) as mock_json_parser_class:
                            # Create a mock parser instance with a mock invoke method
                            mock_parser = MagicMock()
                            mock_parser.invoke.return_value = {"key": "value"}
                            mock_json_parser_class.return_value = mock_parser

                            # Test with a simple message
                            data = {"messages": [{"role": "user", "content": "Hello"}]}
                            result = component.invoke(mock_message_fixture, data)

                            # Check the result
                            assert result == {"key": "value"}
                            mock_parser.invoke.assert_called_once_with(
                                '{"key": "value"}'
                            )

    def test_json_format_error(self, mock_message_fixture):
        """Test error handling for invalid JSON."""
        with patch.object(
            LangChainChatModelBase, "load_component"
        ) as mock_load_component:
            with patch.object(
                LangChainChatModelBase, "create_component"
            ) as mock_create_component:
                with patch.object(
                    LangChainChatModelBase, "validate_config"
                ) as mock_validate_config:
                    # Mock the component class and instance
                    mock_component_class = MagicMock()
                    mock_component = MagicMock()
                    mock_load_component.return_value = mock_component_class
                    mock_create_component.return_value = mock_component
                    mock_validate_config.return_value = None

                    # Mock get_config to return expected values
                    with patch.object(
                        LangChainChatModelBase, "get_config"
                    ) as mock_get_config:

                        def side_effect(key, default=None):
                            if key == "llm_mode":
                                return "none"
                            elif key == "stream_to_flow":
                                return ""
                            elif key == "stream_batch_size":
                                return 15
                            elif key == "component_name":
                                return "test_component"
                            elif key == "component_config":
                                return {
                                    "langchain_module": "test_module",
                                    "langchain_class": "TestClass",
                                    "langchain_component_config": {},
                                }
                            elif key == "llm_response_format":
                                return "json"
                            return default

                        mock_get_config.side_effect = side_effect

                        # Initialize the component
                        component = LangChainChatModelBase(info=info_base, config={})

                        # Mock invoke_model to return a response
                        # This needs to be done AFTER component initialization
                        Result = namedtuple("Result", ["content", "response_uuid"])
                        component.invoke_model = MagicMock(
                            return_value=Result("Invalid JSON", "test-uuid")
                        )

                        # Mock JSON parser to raise an exception
                        # We need to patch at the module level where it's imported
                        with patch(
                            "solace_ai_connector.components.general.llm.langchain.langchain_chat_model_base.JsonOutputParser"
                        ) as mock_json_parser_class:
                            # Create a mock parser instance with a mock invoke method that raises an exception
                            mock_parser = MagicMock()
                            mock_parser.invoke.side_effect = Exception("Invalid JSON")
                            mock_json_parser_class.return_value = mock_parser

                            # Test with a simple message
                            data = {"messages": [{"role": "user", "content": "Hello"}]}
                            with pytest.raises(ValueError) as excinfo:
                                component.invoke(mock_message_fixture, data)

                            assert "Error parsing LLM JSON response" in str(
                                excinfo.value
                            )

    def test_yaml_format_response(self, mock_message_fixture):
        """Test YAML format response."""
        with patch.object(
            LangChainChatModelBase, "load_component"
        ) as mock_load_component:
            with patch.object(
                LangChainChatModelBase, "create_component"
            ) as mock_create_component:
                with patch.object(
                    LangChainChatModelBase, "validate_config"
                ) as mock_validate_config:
                    # Mock the component class and instance
                    mock_component_class = MagicMock()
                    mock_component = MagicMock()
                    mock_load_component.return_value = mock_component_class
                    mock_create_component.return_value = mock_component
                    mock_validate_config.return_value = None

                    # Mock get_config to return expected values
                    with patch.object(
                        LangChainChatModelBase, "get_config"
                    ) as mock_get_config:

                        def side_effect(key, default=None):
                            if key == "llm_mode":
                                return "none"
                            elif key == "stream_to_flow":
                                return ""
                            elif key == "stream_batch_size":
                                return 15
                            elif key == "component_name":
                                return "test_component"
                            elif key == "component_config":
                                return {
                                    "langchain_module": "test_module",
                                    "langchain_class": "TestClass",
                                    "langchain_component_config": {},
                                }
                            elif key == "llm_response_format":
                                return "yaml"
                            return default

                        mock_get_config.side_effect = side_effect

                        # Initialize the component
                        component = LangChainChatModelBase(info=info_base, config={})

                        # Mock invoke_model to return a response
                        # This needs to be done AFTER component initialization
                        Result = namedtuple("Result", ["content", "response_uuid"])
                        component.invoke_model = MagicMock(
                            return_value=Result("key: value", "test-uuid")
                        )

                        # Mock YAML parsing
                        # We need to patch at the module level
                        with patch(
                            "solace_ai_connector.components.general.llm.langchain.langchain_chat_model_base.get_obj_text"
                        ) as mock_get_obj_text:
                            with patch(
                                "solace_ai_connector.components.general.llm.langchain.langchain_chat_model_base.yaml.safe_load"
                            ) as mock_yaml_load:
                                mock_get_obj_text.return_value = "key: value"
                                mock_yaml_load.return_value = {"key": "value"}

                                # Test with a simple message
                                data = {
                                    "messages": [{"role": "user", "content": "Hello"}]
                                }
                                result = component.invoke(mock_message_fixture, data)

                                # Check the result
                                assert result == {"key": "value"}
                                mock_get_obj_text.assert_called_once_with(
                                    "yaml", "key: value"
                                )
                                mock_yaml_load.assert_called_once_with("key: value")

    def test_yaml_format_error(self, mock_message_fixture):
        """Test error handling for invalid YAML."""
        with patch.object(
            LangChainChatModelBase, "load_component"
        ) as mock_load_component:
            with patch.object(
                LangChainChatModelBase, "create_component"
            ) as mock_create_component:
                with patch.object(
                    LangChainChatModelBase, "validate_config"
                ) as mock_validate_config:
                    # Mock the component class and instance
                    mock_component_class = MagicMock()
                    mock_component = MagicMock()
                    mock_load_component.return_value = mock_component_class
                    mock_create_component.return_value = mock_component
                    mock_validate_config.return_value = None

                    # Mock get_config to return expected values
                    with patch.object(
                        LangChainChatModelBase, "get_config"
                    ) as mock_get_config:

                        def side_effect(key, default=None):
                            if key == "llm_mode":
                                return "none"
                            elif key == "stream_to_flow":
                                return ""
                            elif key == "stream_batch_size":
                                return 15
                            elif key == "component_name":
                                return "test_component"
                            elif key == "component_config":
                                return {
                                    "langchain_module": "test_module",
                                    "langchain_class": "TestClass",
                                    "langchain_component_config": {},
                                }
                            elif key == "llm_response_format":
                                return "yaml"
                            return default

                        mock_get_config.side_effect = side_effect

                        # Initialize the component
                        component = LangChainChatModelBase(info=info_base, config={})

                        # Mock invoke_model to return a response
                        # This needs to be done AFTER component initialization
                        Result = namedtuple("Result", ["content", "response_uuid"])
                        component.invoke_model = MagicMock(
                            return_value=Result("Invalid YAML", "test-uuid")
                        )

                        # Mock YAML parsing to raise an exception
                        # We need to patch at the module level
                        with patch(
                            "solace_ai_connector.components.general.llm.langchain.langchain_chat_model_base.get_obj_text"
                        ) as mock_get_obj_text:
                            with patch(
                                "solace_ai_connector.components.general.llm.langchain.langchain_chat_model_base.yaml.safe_load"
                            ) as mock_yaml_load:
                                mock_get_obj_text.return_value = "Invalid YAML"
                                mock_yaml_load.side_effect = Exception("Invalid YAML")

                                # Test with a simple message
                                data = {
                                    "messages": [{"role": "user", "content": "Hello"}]
                                }
                                with pytest.raises(ValueError) as excinfo:
                                    component.invoke(mock_message_fixture, data)

                                assert "Error parsing LLM YAML response" in str(
                                    excinfo.value
                                )
