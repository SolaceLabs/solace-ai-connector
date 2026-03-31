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
        registry = MetricRegistry.initialize(config)

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
        registry = MetricRegistry.initialize(config)

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
        registry = MetricRegistry.initialize(config)

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
        registry = MetricRegistry.initialize(config)

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


class TestLiteLLMHistogramRecording:
    """Test histogram recording for GenAI operation duration."""

    def test_histogram_records_latency_for_non_streaming(self, valid_load_balancer_config):
        """Test that gen_ai.client.operation.duration histogram records latency."""
        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics',
                    'distribution_metrics': {
                        'gen_ai.client.operation.duration': {
                            'exclude_labels': []
                        }
                    }
                }
            }
        }
        MetricRegistry.reset()
        registry = MetricRegistry.initialize(config)

        with patch(
            "solace_ai_connector.components.general.llm.litellm.litellm_base.litellm.Router"
        ):
            mock_response = MagicMock()
            mock_response.choices[0].message.content = "Response"
            mock_response.usage.prompt_tokens = 100
            mock_response.usage.completion_tokens = 50
            mock_response.usage.total_tokens = 150

            with patch.object(LiteLLMChatModelBase, "load_balance") as mock_load_balance:
                mock_load_balance.return_value = mock_response

                with patch("solace_ai_connector.components.general.llm.litellm.litellm_chat_model_base.cost_per_token") as mock_cost:
                    mock_cost.return_value = (0.01, 0.02)

                    component = LiteLLMChatModelBase(
                        info=litellm_chat_info_base,
                        config={"load_balancer": valid_load_balancer_config},
                        instance_name="TestAgent",
                        flow_name="TestAgent"
                    )
                    component.load_balancer_config = valid_load_balancer_config
                    component.send_metrics = MagicMock()

                    # Mock histogram recorder
                    duration_recorder = registry.duration_recorders.get('gen_ai.client.operation.duration')
                    assert duration_recorder is not None, "Histogram recorder should exist"

                    mock_histogram = Mock()
                    duration_recorder._histogram = mock_histogram

                    messages = [{"role": "user", "content": "Test"}]
                    component.invoke_non_stream(messages)

                    # Verify histogram.record was called
                    mock_histogram.record.assert_called_once()
                    call_args = mock_histogram.record.call_args

                    # Verify duration was recorded (should be > 0)
                    duration = call_args[0][0]
                    assert duration >= 0, "Duration should be non-negative"

                    # Verify labels include model and error.type='none'
                    labels = call_args[1]['attributes']
                    assert labels['gen_ai.request.model'] == 'test-model'
                    assert labels['error.type'] == 'none'

    def test_histogram_records_error_type_on_exception(self, valid_load_balancer_config):
        """Test that histogram records error.type when exception occurs."""
        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics',
                    'distribution_metrics': {
                        'gen_ai.client.operation.duration': {
                            'exclude_labels': []
                        }
                    }
                }
            }
        }
        MetricRegistry.reset()
        registry = MetricRegistry.initialize(config)

        with patch(
            "solace_ai_connector.components.general.llm.litellm.litellm_base.litellm.Router"
        ):
            with patch.object(LiteLLMChatModelBase, "load_balance") as mock_load_balance:
                # Simulate an error
                mock_load_balance.side_effect = TimeoutError("LLM timeout")

                component = LiteLLMChatModelBase(
                    info=litellm_chat_info_base,
                    config={"load_balancer": valid_load_balancer_config},
                    instance_name="TestAgent",
                    flow_name="TestAgent"
                )
                component.load_balancer_config = valid_load_balancer_config
                component.send_metrics = MagicMock()

                # Mock histogram recorder
                duration_recorder = registry.duration_recorders.get('gen_ai.client.operation.duration')
                mock_histogram = Mock()
                duration_recorder._histogram = mock_histogram

                messages = [{"role": "user", "content": "Test"}]

                # Should raise but still record histogram
                with pytest.raises(TimeoutError):
                    component.invoke_non_stream(messages)

                # Verify histogram recorded with error.type='timeout'
                mock_histogram.record.assert_called_once()
                labels = mock_histogram.record.call_args[1]['attributes']
                assert labels['error.type'] == 'timeout'


class TestLiteLLMTokenBucketization:
    """Test token bucketization in histogram labels."""

    @pytest.mark.parametrize("token_count,expected_bucket", [
        (100, "1000"),
        (1000, "1000"),
        (1001, "5000"),
        (5000, "5000"),
        (5001, "10000"),
        (10000, "10000"),
        (10001, "50000"),
        (50000, "50000"),
        (50001, "100000"),
        (100000, "100000"),
        (100001, "200000"),
        (500000, "200000"),
    ])
    def test_token_bucketization_in_histogram_labels(self, valid_load_balancer_config, token_count, expected_bucket):
        """Test that monitor.set_prompt_tokens() bucketizes correctly in histogram labels."""
        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics',
                    'distribution_metrics': {
                        'gen_ai.client.operation.duration': {
                            'exclude_labels': []
                        }
                    }
                }
            }
        }
        MetricRegistry.reset()
        registry = MetricRegistry.initialize(config)

        with patch(
            "solace_ai_connector.components.general.llm.litellm.litellm_base.litellm.Router"
        ):
            mock_response = MagicMock()
            mock_response.choices[0].message.content = "Response"
            mock_response.usage.prompt_tokens = token_count
            mock_response.usage.completion_tokens = 50
            mock_response.usage.total_tokens = token_count + 50

            with patch.object(LiteLLMChatModelBase, "load_balance") as mock_load_balance:
                mock_load_balance.return_value = mock_response

                with patch("solace_ai_connector.components.general.llm.litellm.litellm_chat_model_base.cost_per_token") as mock_cost:
                    mock_cost.return_value = (0.01, 0.02)

                    component = LiteLLMChatModelBase(
                        info=litellm_chat_info_base,
                        config={"load_balancer": valid_load_balancer_config},
                        instance_name="TestAgent",
                        flow_name="TestAgent"
                    )
                    component.load_balancer_config = valid_load_balancer_config
                    component.send_metrics = MagicMock()

                    # Mock histogram recorder
                    duration_recorder = registry.duration_recorders.get('gen_ai.client.operation.duration')
                    mock_histogram = Mock()
                    duration_recorder._histogram = mock_histogram

                    messages = [{"role": "user", "content": "Test"}]
                    component.invoke_non_stream(messages)

                    # Verify tokens label has correct bucket
                    labels = mock_histogram.record.call_args[1]['attributes']
                    assert labels['tokens'] == expected_bucket, f"Expected bucket {expected_bucket} for {token_count} tokens"


class TestLiteLLMTTFTRecording:
    """Test Time-To-First-Token (TTFT) histogram recording."""

    def test_ttft_recorded_on_successful_stream(self, valid_load_balancer_config):
        """Test that gen_ai.client.operation.ttft.duration histogram is recorded in streaming mode."""
        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics',
                    'distribution_metrics': {
                        'gen_ai.client.operation.duration': {
                            'exclude_labels': []
                        },
                        'gen_ai.client.operation.ttft.duration': {
                            'exclude_labels': []
                        }
                    }
                }
            }
        }
        MetricRegistry.reset()
        registry = MetricRegistry.initialize(config)

        with patch(
            "solace_ai_connector.components.general.llm.litellm.litellm_base.litellm.Router"
        ):
            # Create streaming response chunks
            chunk1 = MagicMock()
            chunk1.choices[0].delta.content = "First"
            delattr(chunk1, 'usage')

            chunk2 = MagicMock()
            chunk2.choices[0].delta.content = " token"
            delattr(chunk2, 'usage')

            chunk3 = MagicMock()
            chunk3.choices[0].delta.content = None
            chunk3.usage.prompt_tokens = 100
            chunk3.usage.completion_tokens = 20
            chunk3.usage.total_tokens = 120

            mock_response = iter([chunk1, chunk2, chunk3])

            with patch.object(LiteLLMChatModelBase, "load_balance") as mock_load_balance:
                mock_load_balance.return_value = mock_response

                with patch("solace_ai_connector.components.general.llm.litellm.litellm_chat_model_base.cost_per_token") as mock_cost:
                    mock_cost.return_value = (0.01, 0.02)

                    component = LiteLLMChatModelBase(
                        info=litellm_chat_info_base,
                        config={"load_balancer": valid_load_balancer_config},
                        instance_name="StreamAgent",
                        flow_name="StreamAgent"
                    )
                    component.load_balancer_config = valid_load_balancer_config
                    component.send_metrics = MagicMock()
                    component.stream_to_next_component = True
                    component.stream_batch_size = 15

                    # Mock TTFT histogram recorder
                    ttft_recorder = registry.duration_recorders.get('gen_ai.client.operation.ttft.duration')
                    assert ttft_recorder is not None, "TTFT histogram recorder should exist"

                    mock_ttft_histogram = Mock()
                    ttft_recorder._histogram = mock_ttft_histogram

                    test_message = Message(payload={"text": "test"})

                    messages = [{"role": "user", "content": "Test"}]
                    component.invoke_stream(test_message, messages)

                    # Verify TTFT histogram was recorded
                    mock_ttft_histogram.record.assert_called_once()
                    call_args = mock_ttft_histogram.record.call_args

                    # Verify duration was recorded
                    duration = call_args[0][0]
                    assert duration >= 0

                    # Verify labels include model and error.type='none' (success)
                    labels = call_args[1]['attributes']
                    assert labels['gen_ai.request.model'] == 'test-model'
                    assert labels['error.type'] == 'none'

    def test_ttft_error_recorded_when_stream_fails_before_first_token(self, valid_load_balancer_config):
        """Test TTFT error recording when stream fails before first token arrives."""
        from litellm import APIConnectionError

        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics',
                    'distribution_metrics': {
                        'gen_ai.client.operation.ttft.duration': {
                            'exclude_labels': []
                        }
                    }
                }
            }
        }
        MetricRegistry.reset()
        registry = MetricRegistry.initialize(config)

        with patch(
            "solace_ai_connector.components.general.llm.litellm.litellm_base.litellm.Router"
        ):
            # Create generator that raises error before yielding first content token
            def error_generator():
                raise APIConnectionError(
                    "Connection failed",
                    llm_provider="test",
                    model="test-model"
                )
                yield  # Never reached

            with patch.object(LiteLLMChatModelBase, "load_balance") as mock_load_balance:
                mock_load_balance.return_value = error_generator()

                component = LiteLLMChatModelBase(
                    info=litellm_chat_info_base,
                    config={"load_balancer": valid_load_balancer_config},
                    instance_name="StreamAgent",
                    flow_name="StreamAgent"
                )
                component.load_balancer_config = valid_load_balancer_config
                component.send_metrics = MagicMock()
                component.stream_to_next_component = True

                # Mock TTFT histogram recorder
                ttft_recorder = registry.duration_recorders.get('gen_ai.client.operation.ttft.duration')
                mock_ttft_histogram = Mock()
                ttft_recorder._histogram = mock_ttft_histogram

                test_message = Message(payload={"text": "test"})

                messages = [{"role": "user", "content": "Test"}]
                result = component.invoke_stream(test_message, messages)

                # Should return error result (not raise)
                assert result['handle_error'] is True

                # Verify TTFT histogram was recorded with error
                mock_ttft_histogram.record.assert_called_once()
                labels = mock_ttft_histogram.record.call_args[1]['attributes']

                # Error type should be set (not 'none')
                assert labels['error.type'] != 'none'
                assert labels['gen_ai.request.model'] == 'test-model'

    def test_ttft_error_recorded_on_generic_exception_before_first_token(self, valid_load_balancer_config):
        """Test TTFT error recording for generic exception before first token."""
        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics',
                    'distribution_metrics': {
                        'gen_ai.client.operation.ttft.duration': {
                            'exclude_labels': []
                        }
                    }
                }
            }
        }
        MetricRegistry.reset()
        registry = MetricRegistry.initialize(config)

        with patch(
            "solace_ai_connector.components.general.llm.litellm.litellm_base.litellm.Router"
        ):
            def error_generator():
                raise ValueError("Unexpected error")
                yield

            with patch.object(LiteLLMChatModelBase, "load_balance") as mock_load_balance:
                mock_load_balance.return_value = error_generator()

                component = LiteLLMChatModelBase(
                    info=litellm_chat_info_base,
                    config={"load_balancer": valid_load_balancer_config},
                    instance_name="StreamAgent",
                    flow_name="StreamAgent"
                )
                component.load_balancer_config = valid_load_balancer_config
                component.send_metrics = MagicMock()
                component.stream_to_next_component = True

                # Mock TTFT histogram recorder
                ttft_recorder = registry.duration_recorders.get('gen_ai.client.operation.ttft.duration')
                mock_ttft_histogram = Mock()
                ttft_recorder._histogram = mock_ttft_histogram

                test_message = Message(payload={"text": "test"})

                messages = [{"role": "user", "content": "Test"}]

                # Generic exception should propagate
                with pytest.raises(ValueError):
                    component.invoke_stream(test_message, messages)

                # Verify TTFT histogram was recorded with error
                mock_ttft_histogram.record.assert_called_once()
                labels = mock_ttft_histogram.record.call_args[1]['attributes']
                assert labels['error.type'] == 'ValueError'


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
        registry = MetricRegistry.initialize(config)

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
        registry = MetricRegistry.initialize(config)

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
