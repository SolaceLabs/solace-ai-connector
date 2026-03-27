"""Unit tests for observability value metrics."""

import pytest
from unittest.mock import Mock
from solace_ai_connector.common.observability.registry import MetricRegistry
from solace_ai_connector.common.observability.config import (
    DEFAULT_VALUE_METRICS,
    validate_config
)
from solace_ai_connector.common.observability.recorders import (
    CounterRecorder,
    NoOpRecorder
)
from solace_ai_connector.common.observability.monitors import (
    GenAITokenMonitor,
    GenAICostMonitor
)


class TestBuiltInValueMetrics:
    """Test built-in value metrics."""

    def test_default_value_metrics_created(self):
        """Test default value metrics created when observability enabled."""
        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics'
                }
            }
        }
        registry = MetricRegistry(config)

        assert 'gen_ai.tokens.used' in registry._value_recorders
        assert 'gen_ai.cost.total' in registry._value_recorders
        assert isinstance(registry._value_recorders['gen_ai.tokens.used'], CounterRecorder)
        assert isinstance(registry._value_recorders['gen_ai.cost.total'], CounterRecorder)

    def test_default_exclude_labels_for_value_metrics(self):
        """Test default exclude_labels applied to value metrics."""
        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics'
                }
            }
        }
        registry = MetricRegistry(config)
        token_recorder = registry._value_recorders['gen_ai.tokens.used']
        assert 'owner.id' in token_recorder._excluded_labels
        cost_recorder = registry._value_recorders['gen_ai.cost.total']
        assert 'owner.id' in cost_recorder._excluded_labels

    def test_value_metrics_disabled_when_observability_disabled(self):
        """Test value metrics not created when observability disabled."""
        config = {}
        registry = MetricRegistry(config)
        assert registry.enabled is False
        assert registry._value_recorders == {}

class TestValueMetricsConfiguration:
    """Test value metrics configuration."""

    def test_override_exclude_labels_include_user_id(self):
        """Test override exclude_labels to include owner.id."""
        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics',
                    'value_metrics': {
                        'gen_ai.tokens.used': {
                            'exclude_labels': []  # Include all labels
                        }
                    }
                }
            }
        }
        registry = MetricRegistry(config)
        token_recorder = registry._value_recorders['gen_ai.tokens.used']
        assert 'owner.id' not in token_recorder._excluded_labels

    def test_disable_value_metric_with_wildcard(self):
        """Test disable value metric with exclude_labels: ['*']."""
        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics',
                    'value_metrics': {
                        'gen_ai.cost.total': {
                            'exclude_labels': ['*']  # Disabled
                        }
                    }
                }
            }
        }
        registry = MetricRegistry(config)
        assert 'gen_ai.cost.total' not in registry._value_recorders
        assert 'gen_ai.tokens.used' in registry._value_recorders

    def test_custom_value_metric_via_create_counter(self):
        """Test custom value metrics via create_counter."""
        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics',
                    'value_metrics': {
                        'my.custom.requests.total': {
                            'exclude_labels': ['request.path']
                        }
                    }
                }
            }
        }
        registry = MetricRegistry(config)
        assert 'gen_ai.tokens.used' in registry._value_recorders
        counter = registry.create_counter('my.custom.requests.total')
        assert isinstance(counter, CounterRecorder)
        assert 'request.path' in counter._excluded_labels

class TestGenAIMonitorClasses:
    """Test GenAI monitor classes."""

    def test_token_monitor_creates_correct_labels(self):
        """Test token monitor creates correct labels."""
        monitor = GenAITokenMonitor.create(
            model="gpt-4",
            component_name="TestAgent",
            owner_id="user@example.com",
            token_type="input"
        )
        assert monitor.monitor_type == "gen_ai.tokens.used"
        assert monitor.labels == {
            "gen_ai.request.model": "gpt-4",
            "component.name": "TestAgent",
            "owner.id": "user@example.com",
            "gen_ai.token.type": "input"
        }
        assert monitor.error_parser is None

    def test_token_monitor_output_type(self):
        """Test token monitor with output type."""
        monitor = GenAITokenMonitor.create(
            model="claude-sonnet-3.5",
            component_name="MyAgent",
            owner_id="anonymous",
            token_type="output"
        )
        assert monitor.labels["gen_ai.token.type"] == "output"

    def test_cost_monitor_creates_correct_labels(self):
        """Test cost monitor creates correct labels."""
        monitor = GenAICostMonitor.create(
            model="gpt-4",
            component_name="TestAgent",
            owner_id="user@example.com"
        )
        assert monitor.monitor_type == "gen_ai.cost.total"
        assert monitor.labels == {
            "gen_ai.request.model": "gpt-4",
            "component.name": "TestAgent",
            "owner.id": "user@example.com"
        }
        assert monitor.error_parser is None

    def test_token_monitor_with_anonymous_user(self):
        """Test token monitor with anonymous user."""
        monitor = GenAITokenMonitor.create(
            model="gpt-4",
            component_name="TestAgent",
            owner_id="anonymous",
            token_type="input"
        )
        assert monitor.labels["owner.id"] == "anonymous"

class TestValueMetricsRecording:
    """Test recording values to counters."""

    def test_record_counter_from_monitor(self):
        """Test record counter from monitor."""
        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics'
                }
            }
        }
        registry = MetricRegistry(config)
        monitor = GenAITokenMonitor.create(
            model="gpt-4",
            component_name="TestAgent",
            owner_id="user123",
            token_type="input"
        )
        recorder = registry._value_recorders['gen_ai.tokens.used']
        mock_counter = Mock()
        recorder._counter = mock_counter
        registry.record_counter_from_monitor(monitor, 100)
        mock_counter.add.assert_called_once()
        call_args = mock_counter.add.call_args
        assert call_args[0][0] == 100
        recorded_labels = call_args[1]['attributes']
        assert 'owner.id' not in recorded_labels
        assert recorded_labels['gen_ai.request.model'] == 'gpt-4'
        assert recorded_labels['component.name'] == 'TestAgent'
        assert recorded_labels['gen_ai.token.type'] == 'input'

    def test_record_counter_includes_user_id_when_not_excluded(self):
        """Test record includes owner.id when not excluded."""
        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics',
                    'value_metrics': {
                        'gen_ai.tokens.used': {
                            'exclude_labels': []  # Include all labels
                        }
                    }
                }
            }
        }
        registry = MetricRegistry(config)

        monitor = GenAITokenMonitor.create(
            model="gpt-4",
            component_name="TestAgent",
            owner_id="user123",
            token_type="output"
        )
        recorder = registry._value_recorders['gen_ai.tokens.used']
        mock_counter = Mock()
        recorder._counter = mock_counter
        registry.record_counter_from_monitor(monitor, 50)
        call_args = mock_counter.add.call_args
        recorded_labels = call_args[1]['attributes']
        assert recorded_labels['owner.id'] == 'user123'
        assert recorded_labels['gen_ai.request.model'] == 'gpt-4'
        assert recorded_labels['component.name'] == 'TestAgent'
        assert recorded_labels['gen_ai.token.type'] == 'output'

    def test_record_cost_counter(self):
        """Test record cost counter."""
        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics',
                    'value_metrics': {
                        'gen_ai.cost.total': {
                            'exclude_labels': []  # Include owner.id for this test
                        }
                    }
                }
            }
        }
        registry = MetricRegistry(config)
        monitor = GenAICostMonitor.create(
            model="gpt-4",
            component_name="TestAgent",
            owner_id="user123"
        )
        recorder = registry._value_recorders['gen_ai.cost.total']
        mock_counter = Mock()
        recorder._counter = mock_counter
        registry.record_counter_from_monitor(monitor, 0.05)
        mock_counter.add.assert_called_once()
        call_args = mock_counter.add.call_args
        assert call_args[0][0] == 0.05
        recorded_labels = call_args[1]['attributes']
        assert recorded_labels['owner.id'] == 'user123'
        assert recorded_labels['gen_ai.request.model'] == 'gpt-4'
        assert recorded_labels['component.name'] == 'TestAgent'

    def test_record_counter_when_disabled_is_noop(self):
        """Test record to disabled counter is noop."""
        config = {
            'management_server': {
                'observability': {
                    'enabled': False
                }
            }
        }
        registry = MetricRegistry(config)

        monitor = GenAITokenMonitor.create(
            model="gpt-4",
            component_name="TestAgent",
            owner_id="user123",
            token_type="input"
        )

        # Should not raise - just no-op
        registry.record_counter_from_monitor(monitor, 100)


class TestValueMetricsValidation:
    """Test validation rules for value_metrics."""

    def test_validation_rejects_buckets_in_value_metrics(self):
        """Test buckets field rejected in value_metrics."""
        obs_config = {
            'enabled': True,
            'value_metrics': {
                'gen_ai.tokens.used': {
                    'buckets': [1, 2, 3],
                    'exclude_labels': []
                }
            }
        }
        with pytest.raises(ValueError, match="value_metrics.gen_ai.tokens.used: only 'exclude_labels' is allowed, got 'buckets'"):
            validate_config(obs_config)

    def test_validation_accepts_only_exclude_labels(self):
        """Test value_metrics only accepts exclude_labels."""
        obs_config = {
            'enabled': True,
            'value_metrics': {
                'gen_ai.cost.total': {
                    'invalid_key': 'value'
                }
            }
        }
        with pytest.raises(ValueError, match="only 'exclude_labels' is allowed"):
            validate_config(obs_config)

    def test_validation_accepts_empty_exclude_labels(self):
        """Test empty exclude_labels is valid."""
        obs_config = {
            'enabled': True,
            'value_metrics': {
                'gen_ai.tokens.used': {
                    'exclude_labels': []
                }
            }
        }
        validate_config(obs_config)

    def test_validation_accepts_wildcard_to_disable(self):
        """Test exclude_labels: ['*'] is valid."""
        obs_config = {
            'enabled': True,
            'value_metrics': {
                'gen_ai.tokens.used': {
                    'exclude_labels': ['*']
                }
            }
        }
        validate_config(obs_config)

class TestEndToEndValueMetrics:
    """End-to-end value metrics tests."""

    def test_complete_workflow_with_multiple_metrics(self):
        """Test workflow with multiple metrics."""
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
                            'exclude_labels': ['owner.id']
                        }
                    }
                }
            }
        }
        registry = MetricRegistry(config)
        token_recorder = registry._value_recorders['gen_ai.tokens.used']
        mock_token_counter = Mock()
        token_recorder._counter = mock_token_counter
        cost_recorder = registry._value_recorders['gen_ai.cost.total']
        mock_cost_counter = Mock()
        cost_recorder._counter = mock_cost_counter
        token_monitor_1 = GenAITokenMonitor.create("gpt-4", "AgentA", "user1", "input")
        registry.record_counter_from_monitor(token_monitor_1, 100)

        cost_monitor_1 = GenAICostMonitor.create("gpt-4", "AgentA", "user1")
        registry.record_counter_from_monitor(cost_monitor_1, 0.05)

        # User 2, Agent A
        token_monitor_2 = GenAITokenMonitor.create("gpt-4", "AgentA", "user2", "output")
        registry.record_counter_from_monitor(token_monitor_2, 50)

        cost_monitor_2 = GenAICostMonitor.create("gpt-4", "AgentA", "user2")
        registry.record_counter_from_monitor(cost_monitor_2, 0.03)
        token_monitor_3 = GenAITokenMonitor.create("claude-sonnet", "AgentB", "user1", "input")
        registry.record_counter_from_monitor(token_monitor_3, 200)
        assert mock_token_counter.add.call_count == 3
        assert mock_cost_counter.add.call_count == 2
        token_call_1 = mock_token_counter.add.call_args_list[0]
        assert token_call_1[1]['attributes']['owner.id'] == 'user1'
        assert token_call_1[1]['attributes']['component.name'] == 'AgentA'
        assert token_call_1[1]['attributes']['gen_ai.token.type'] == 'input'
        cost_call_1 = mock_cost_counter.add.call_args_list[0]
        assert 'owner.id' not in cost_call_1[1]['attributes']
        assert cost_call_1[1]['attributes']['component.name'] == 'AgentA'
        assert cost_call_1[1]['attributes']['gen_ai.request.model'] == 'gpt-4'

    def test_get_recorder_returns_value_metrics(self):
        """Test get_recorder finds value metrics."""
        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics'
                }
            }
        }
        registry = MetricRegistry(config)
        duration_recorder = registry.get_recorder('gen_ai.client.operation.duration')
        assert duration_recorder is not None
        token_recorder = registry.get_recorder('gen_ai.tokens.used')
        assert token_recorder is not None
        cost_recorder = registry.get_recorder('gen_ai.cost.total')
        assert cost_recorder is not None
        assert registry.get_recorder('non.existent.metric') is None
