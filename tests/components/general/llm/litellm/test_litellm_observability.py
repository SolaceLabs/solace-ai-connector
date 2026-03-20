"""Integration tests for LiteLLM observability (token/cost tracking)."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from solace_ai_connector.components.general.llm.litellm.litellm_chat_model_base import (
    LiteLLMChatModelBase,
    litellm_chat_info_base,
)
from solace_ai_connector.common.observability.registry import MetricRegistry
from solace_ai_connector.common.message import Message


class TestLiteLLMNonStreamingObservability:
    """Test token and cost tracking in non-streaming mode."""

    def test_token_counters_recorded_on_successful_call(self, valid_load_balancer_config):
        """Test that input/output token counters are recorded after successful LLM call."""
        # Initialize MetricRegistry with observability enabled
        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics',
                    'value_metrics': {
                        'gen_ai.tokens.used': {
                            'exclude_labels': []  # Include owner.id for verification
                        },
                        'gen_ai.cost.total': {
                            'exclude_labels': []
                        }
                    }
                }
            }
        }
        MetricRegistry.reset()  # Clear any previous instance
        registry = MetricRegistry(config)

        with patch(
            "solace_ai_connector.components.general.llm.litellm.litellm_base.litellm.Router"
        ):
            # Setup mock response
            mock_response = MagicMock()
            mock_response.choices[0].message.content = "Test response"
            mock_response.usage.prompt_tokens = 150
            mock_response.usage.completion_tokens = 75
            mock_response.usage.total_tokens = 225

            with patch.object(LiteLLMChatModelBase, "load_balance") as mock_load_balance:
                mock_load_balance.return_value = mock_response

                with patch("solace_ai_connector.components.general.llm.litellm.litellm_chat_model_base.cost_per_token") as mock_cost:
                    mock_cost.return_value = (0.015, 0.045)  # Input cost, output cost

                    component = LiteLLMChatModelBase(
                        info=litellm_chat_info_base,
                        config={"load_balancer": valid_load_balancer_config},
                        instance_name="TestAgent",
                        flow_name="TestAgent"  # Set flow_name for component.name label
                    )
                    component.load_balancer_config = valid_load_balancer_config
                    component.send_metrics = MagicMock()

                    # Set current_message with user_properties
                    test_message = Message(
                        payload={"text": "test"},
                        user_properties={"userId": "test_user"}
                    )
                    component.current_message = test_message

                    # Mock token counter recorder to verify calls
                    token_recorder = registry._value_recorders['gen_ai.tokens.used']
                    mock_token_counter = Mock()
                    token_recorder._counter = mock_token_counter

                    # Mock cost counter recorder
                    cost_recorder = registry._value_recorders['gen_ai.cost.total']
                    mock_cost_counter = Mock()
                    cost_recorder._counter = mock_cost_counter

                    # Execute
                    messages = [{"role": "user", "content": "Hello"}]
                    result = component.invoke_non_stream(messages)

                    # Verify response
                    assert result == {"content": "Test response"}

                    # Verify token counter was called twice (input + output)
                    assert mock_token_counter.add.call_count == 2

                    # Verify input tokens recorded
                    input_call = mock_token_counter.add.call_args_list[0]
                    assert input_call[0][0] == 150  # prompt_tokens
                    input_labels = input_call[1]['attributes']
                    assert input_labels['gen_ai.request.model'] == 'test-model'
                    assert input_labels['component.name'] == 'TestAgent'
                    assert input_labels['owner.id'] == 'test_user'
                    assert input_labels['gen_ai.token.type'] == 'input'

                    # Verify output tokens recorded
                    output_call = mock_token_counter.add.call_args_list[1]
                    assert output_call[0][0] == 75  # completion_tokens
                    output_labels = output_call[1]['attributes']
                    assert output_labels['gen_ai.token.type'] == 'output'

                    # Verify cost counter called once
                    mock_cost_counter.add.assert_called_once()
                    cost_call = mock_cost_counter.add.call_args
                    assert cost_call[0][0] == 0.06  # 0.015 + 0.045
                    cost_labels = cost_call[1]['attributes']
                    assert cost_labels['gen_ai.request.model'] == 'test-model'
                    assert cost_labels['component.name'] == 'TestAgent'
                    assert cost_labels['owner.id'] == 'test_user'

    def test_anonymous_user_when_no_user_properties(self, valid_load_balancer_config):
        """Test that owner.id defaults to 'none' when no user_properties."""
        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics',
                    'value_metrics': {
                        'gen_ai.tokens.used': {
                            'exclude_labels': []
                        }
                    }
                }
            }
        }
        MetricRegistry.reset()
        registry = MetricRegistry(config)

        with patch(
            "solace_ai_connector.components.general.llm.litellm.litellm_base.litellm.Router"
        ):
            mock_response = MagicMock()
            mock_response.choices[0].message.content = "Response"
            mock_response.usage.prompt_tokens = 10
            mock_response.usage.completion_tokens = 5
            mock_response.usage.total_tokens = 15

            with patch.object(LiteLLMChatModelBase, "load_balance") as mock_load_balance:
                mock_load_balance.return_value = mock_response

                with patch("solace_ai_connector.components.general.llm.litellm.litellm_chat_model_base.cost_per_token") as mock_cost:
                    mock_cost.return_value = (0.01, 0.02)

                    component = LiteLLMChatModelBase(
                        info=litellm_chat_info_base,
                        config={"load_balancer": valid_load_balancer_config},
                        instance_name="TestAgent",
                        flow_name="TestAgent"  # Set flow_name for component.name label
                    )
                    component.load_balancer_config = valid_load_balancer_config
                    component.send_metrics = MagicMock()
                    component.current_message = None  # No message = anonymous

                    # Mock counter
                    token_recorder = registry._value_recorders['gen_ai.tokens.used']
                    mock_counter = Mock()
                    token_recorder._counter = mock_counter

                    messages = [{"role": "user", "content": "Hello"}]
                    component.invoke_non_stream(messages)

                    # Verify owner.id is 'none' (no user context in connector flows)
                    call_args = mock_counter.add.call_args_list[0]
                    labels = call_args[1]['attributes']
                    assert labels['owner.id'] == 'none'

    def test_metrics_recording_does_not_break_llm_call_on_error(self, valid_load_balancer_config):
        """Test that errors in metrics recording don't break LLM calls."""
        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics'
                }
            }
        }
        MetricRegistry.reset()
        registry = MetricRegistry(config)

        with patch(
            "solace_ai_connector.components.general.llm.litellm.litellm_base.litellm.Router"
        ):
            mock_response = MagicMock()
            mock_response.choices[0].message.content = "Response"
            mock_response.usage.prompt_tokens = 10
            mock_response.usage.completion_tokens = 5
            mock_response.usage.total_tokens = 15

            with patch.object(LiteLLMChatModelBase, "load_balance") as mock_load_balance:
                mock_load_balance.return_value = mock_response

                # Make cost_per_token raise an error
                with patch("solace_ai_connector.components.general.llm.litellm.litellm_chat_model_base.cost_per_token") as mock_cost:
                    mock_cost.side_effect = Exception("Cost calculation failed")

                    component = LiteLLMChatModelBase(
                        info=litellm_chat_info_base,
                        config={"load_balancer": valid_load_balancer_config},
                        instance_name="TestAgent",
                        flow_name="TestAgent"  # Set flow_name for component.name label
                    )
                    component.load_balancer_config = valid_load_balancer_config
                    component.send_metrics = MagicMock()

                    messages = [{"role": "user", "content": "Hello"}]
                    result = component.invoke_non_stream(messages)

                    # LLM call should still succeed despite metrics error
                    assert result == {"content": "Response"}


class TestLiteLLMStreamingObservability:
    """Test token and cost tracking in streaming mode."""

    def test_token_counters_recorded_in_streaming_mode(self, valid_load_balancer_config):
        """Test that token/cost counters are recorded in streaming mode."""
        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics',
                    'value_metrics': {
                        'gen_ai.tokens.used': {
                            'exclude_labels': []
                        },
                        'gen_ai.cost.total': {
                            'exclude_labels': []
                        }
                    }
                }
            }
        }
        MetricRegistry.reset()
        registry = MetricRegistry(config)

        with patch(
            "solace_ai_connector.components.general.llm.litellm.litellm_base.litellm.Router"
        ):
            # Create streaming response chunks
            chunk1 = MagicMock()
            chunk1.choices[0].delta.content = "Hello"
            delattr(chunk1, 'usage')  # First chunk has no usage

            chunk2 = MagicMock()
            chunk2.choices[0].delta.content = " world"
            delattr(chunk2, 'usage')

            chunk3 = MagicMock()
            chunk3.choices[0].delta.content = None  # End of stream
            chunk3.usage.prompt_tokens = 100
            chunk3.usage.completion_tokens = 50
            chunk3.usage.total_tokens = 150

            mock_response = iter([chunk1, chunk2, chunk3])

            with patch.object(LiteLLMChatModelBase, "load_balance") as mock_load_balance:
                mock_load_balance.return_value = mock_response

                with patch("solace_ai_connector.components.general.llm.litellm.litellm_chat_model_base.cost_per_token") as mock_cost:
                    mock_cost.return_value = (0.01, 0.03)

                    component = LiteLLMChatModelBase(
                        info=litellm_chat_info_base,
                        config={"load_balancer": valid_load_balancer_config},
                        instance_name="StreamingAgent",
                        flow_name="StreamingAgent"  # Set flow_name for component.name label
                    )
                    component.load_balancer_config = valid_load_balancer_config
                    component.send_metrics = MagicMock()
                    component.stream_to_next_component = True
                    component.stream_batch_size = 15

                    test_message = Message(
                        payload={"text": "test"},
                        user_properties={"userId": "streaming_user"}
                    )
                    component.current_message = test_message

                    # Mock counters
                    token_recorder = registry._value_recorders['gen_ai.tokens.used']
                    mock_token_counter = Mock()
                    token_recorder._counter = mock_token_counter

                    cost_recorder = registry._value_recorders['gen_ai.cost.total']
                    mock_cost_counter = Mock()
                    cost_recorder._counter = mock_cost_counter

                    # Execute streaming
                    messages = [{"role": "user", "content": "Hello"}]
                    result = component.invoke_stream(test_message, messages)

                    # Verify tokens recorded
                    assert mock_token_counter.add.call_count == 2  # Input + output

                    # Verify input tokens
                    input_call = mock_token_counter.add.call_args_list[0]
                    assert input_call[0][0] == 100
                    assert input_call[1]['attributes']['gen_ai.token.type'] == 'input'
                    assert input_call[1]['attributes']['owner.id'] == 'streaming_user'

                    # Verify output tokens
                    output_call = mock_token_counter.add.call_args_list[1]
                    assert output_call[0][0] == 50
                    assert output_call[1]['attributes']['gen_ai.token.type'] == 'output'

                    # Verify cost recorded
                    mock_cost_counter.add.assert_called_once()
                    assert mock_cost_counter.add.call_args[0][0] == 0.04  # 0.01 + 0.03


class TestLiteLLMLabelFiltering:
    """Test label filtering behavior in LiteLLM integration."""

    def test_user_id_filtered_by_default(self, valid_load_balancer_config):
        """Test that owner.id is filtered out by default configuration."""
        # Use default config (owner.id excluded)
        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics'
                    # Default value_metrics has exclude_labels: ["owner.id"]
                }
            }
        }
        MetricRegistry.reset()
        registry = MetricRegistry(config)

        with patch(
            "solace_ai_connector.components.general.llm.litellm.litellm_base.litellm.Router"
        ):
            mock_response = MagicMock()
            mock_response.choices[0].message.content = "Response"
            mock_response.usage.prompt_tokens = 10
            mock_response.usage.completion_tokens = 5
            mock_response.usage.total_tokens = 15

            with patch.object(LiteLLMChatModelBase, "load_balance") as mock_load_balance:
                mock_load_balance.return_value = mock_response

                with patch("solace_ai_connector.components.general.llm.litellm.litellm_chat_model_base.cost_per_token") as mock_cost:
                    mock_cost.return_value = (0.001, 0.002)

                    component = LiteLLMChatModelBase(
                        info=litellm_chat_info_base,
                        config={"load_balancer": valid_load_balancer_config},
                        instance_name="TestAgent",
                        flow_name="TestAgent"  # Set flow_name for component.name label
                    )
                    component.load_balancer_config = valid_load_balancer_config
                    component.send_metrics = MagicMock()

                    test_message = Message(
                        payload={"text": "test"},
                        user_properties={"userId": "filtered_user"}
                    )
                    component.current_message = test_message

                    # Mock counter
                    token_recorder = registry._value_recorders['gen_ai.tokens.used']
                    mock_counter = Mock()
                    token_recorder._counter = mock_counter

                    messages = [{"role": "user", "content": "Test"}]
                    component.invoke_non_stream(messages)

                    # Verify owner.id was filtered out
                    call_args = mock_counter.add.call_args_list[0]
                    labels = call_args[1]['attributes']
                    assert 'owner.id' not in labels  # Filtered by default
                    assert labels['component.name'] == 'TestAgent'
                    assert labels['gen_ai.request.model'] == 'test-model'

    def test_metrics_disabled_when_observability_disabled(self, valid_load_balancer_config):
        """Test that no metrics are recorded when observability is disabled."""
        config = {}  # No observability config = disabled
        MetricRegistry.reset()
        registry = MetricRegistry(config)

        with patch(
            "solace_ai_connector.components.general.llm.litellm.litellm_base.litellm.Router"
        ):
            mock_response = MagicMock()
            mock_response.choices[0].message.content = "Response"
            mock_response.usage.prompt_tokens = 10
            mock_response.usage.completion_tokens = 5
            mock_response.usage.total_tokens = 15

            with patch.object(LiteLLMChatModelBase, "load_balance") as mock_load_balance:
                mock_load_balance.return_value = mock_response

                component = LiteLLMChatModelBase(
                    info=litellm_chat_info_base,
                    config={"load_balancer": valid_load_balancer_config},
                    instance_name="TestAgent"
                )
                component.load_balancer_config = valid_load_balancer_config
                component.send_metrics = MagicMock()

                messages = [{"role": "user", "content": "Test"}]
                result = component.invoke_non_stream(messages)

                # LLM call succeeds
                assert result == {"content": "Response"}

                # No value recorders exist (observability disabled)
                assert registry._value_recorders == {}
