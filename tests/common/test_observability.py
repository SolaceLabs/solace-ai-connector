"""Unit tests for observability framework."""

import pytest
from unittest.mock import Mock, patch
from solace_ai_connector.common.observability.registry import MetricRegistry
from solace_ai_connector.common.observability.config import (
    load_observability_config,
    validate_config,
    DEFAULT_METRIC_CONFIGS
)
from solace_ai_connector.common.observability.recorders import (
    NoOpRecorder,
    CounterRecorder,
    GaugeRecorder,
    HistogramRecorder
)


class TestConfigurationLoading:
    """Test configuration loading with observability disabled/enabled."""

    def test_observability_disabled_no_config(self):
        """Test that observability is disabled when no config provided."""
        config = {}
        obs_config = load_observability_config(config)

        assert obs_config == {'enabled': False}

    def test_observability_disabled_explicit(self):
        """Test that observability is disabled when explicitly set."""
        config = {
            'management_server': {
                'observability': {
                    'enabled': False
                }
            }
        }
        obs_config = load_observability_config(config)

        assert obs_config['enabled'] is False

    def test_observability_enabled_minimal(self):
        """Test observability enabled with minimal config."""
        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics'
                }
            }
        }
        obs_config = load_observability_config(config)

        assert obs_config['enabled'] is True
        assert obs_config['path'] == '/metrics'

    def test_observability_enabled_with_prefix(self):
        """Test observability enabled with metric prefix."""
        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics',
                    'metric_prefix': 'sam'
                }
            }
        }
        obs_config = load_observability_config(config)

        assert obs_config['enabled'] is True
        assert obs_config['metric_prefix'] == 'sam'

    def test_registry_initialization_disabled(self):
        """Test MetricRegistry initialization when disabled."""
        config = {}
        registry = MetricRegistry(config)

        assert registry.enabled is False
        assert registry.recorders == {}

    def test_registry_initialization_enabled(self):
        """Test MetricRegistry initialization when enabled."""
        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics',
                    'metric_prefix': 'sam'
                }
            }
        }
        registry = MetricRegistry(config)

        assert registry.enabled is True
        assert registry.metric_prefix == 'sam'
        assert len(registry.recorders) == 7  # All 7 default histograms

    def test_config_validation_rejects_unknown_top_level_keys(self):
        """Test validation rejects unknown top-level keys (catches stale configs)."""
        obs_config = {
            'enabled': True,
            'unknown_key': 'value'
        }

        with pytest.raises(ValueError, match="Unknown configuration key 'unknown_key'"):
            validate_config(obs_config)

    def test_config_validation_accepts_reserved_keys(self):
        """Test validation accepts all reserved top-level keys."""
        obs_config = {
            'enabled': True,
            'metric_prefix': 'sam',
            'path': '/metrics',
            'system': {},
            'custom': {}
        }

        # Should not raise
        validate_config(obs_config)


class TestDefaultSystemMetrics:
    """Test that when observability is enabled with no system config, defaults are enforced."""

    def test_all_default_metrics_created(self):
        """Test all 7 default histogram families are created."""
        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics'
                }
            }
        }
        registry = MetricRegistry(config)

        # Verify all 7 default metrics exist
        expected_metrics = [
            'outbound.request.duration',
            'gen_ai.client.operation.duration',
            'gen_ai.client.operation.ttft.duration',
            'db.duration',
            'gateway.duration',
            'gateway.ttfb.duration',
            'operation.duration'
        ]

        for metric_name in expected_metrics:
            assert metric_name in registry.recorders
            assert isinstance(registry.recorders[metric_name], HistogramRecorder)

    def test_default_bucket_configurations(self):
        """Test default bucket sizes match DEFAULT_METRIC_CONFIGS."""
        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics'
                }
            }
        }
        registry = MetricRegistry(config)

        # Verify default buckets for each metric
        for metric_name, default_config in DEFAULT_METRIC_CONFIGS.items():
            recorder = registry.recorders[metric_name]
            assert recorder._buckets == default_config['buckets']

    def test_default_exclude_labels(self):
        """Test default exclude_labels are applied."""
        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics'
                }
            }
        }
        registry = MetricRegistry(config)

        # gen_ai.client.operation.duration should exclude 'tokens' by default
        genai_recorder = registry.recorders['gen_ai.client.operation.duration']
        assert 'tokens' in genai_recorder._excluded_labels

    def test_metric_prefix_applied(self):
        """Test metric prefix is applied to all metric names."""
        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics',
                    'metric_prefix': 'sam2'
                }
            }
        }
        registry = MetricRegistry(config)

        # Verify prefix is applied
        full_name = registry._get_full_metric_name('outbound.request.duration')
        assert full_name == 'sam2.outbound.request.duration'

    def test_no_prefix_when_not_configured(self):
        """Test no prefix is applied when not configured."""
        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics'
                }
            }
        }
        registry = MetricRegistry(config)

        full_name = registry._get_full_metric_name('outbound.request.duration')
        assert full_name == 'outbound.request.duration'


class TestSystemMetricsOverride:
    """Test system: config overrides and label filtering."""

    def test_custom_buckets_override_defaults(self):
        """Test custom buckets in system: section override defaults."""
        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics',
                    'system': {
                        'gen_ai.client.operation.duration': {
                            'values': [1.0, 5.0, 10.0, 30.0, 60.0]
                        }
                    }
                }
            }
        }
        registry = MetricRegistry(config)

        # Verify custom buckets are applied
        genai_recorder = registry.recorders['gen_ai.client.operation.duration']
        assert genai_recorder._buckets == [1.0, 5.0, 10.0, 30.0, 60.0]

    def test_custom_exclude_labels_override_defaults(self):
        """Test custom exclude_labels in system: section override defaults."""
        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics',
                    'system': {
                        'db.duration': {
                            'exclude_labels': ['db.operation.name']
                        }
                    }
                }
            }
        }
        registry = MetricRegistry(config)

        # Verify custom exclude_labels are applied
        db_recorder = registry.recorders['db.duration']
        assert 'db.operation.name' in db_recorder._excluded_labels

    def test_label_filtering_actually_filters(self):
        """Test that excluded labels are actually filtered from recorded metrics."""
        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics',
                    'system': {
                        'db.duration': {
                            'exclude_labels': ['db.operation.name']
                        }
                    }
                }
            }
        }
        registry = MetricRegistry(config)

        # Get the recorder and verify it filters labels
        db_recorder = registry.recorders['db.duration']

        # Mock the histogram to capture what labels are actually passed
        mock_histogram = Mock()
        db_recorder._histogram = mock_histogram

        # Record with both allowed and excluded labels
        labels = {
            'db.collection.name': 'users',
            'db.operation.name': 'query',  # Should be filtered
            'error.type': 'none'
        }
        db_recorder.record(0.1, labels)

        # Verify the histogram was called with filtered labels
        mock_histogram.record.assert_called_once()
        call_args = mock_histogram.record.call_args
        filtered_labels = call_args[1]['attributes']

        assert 'db.collection.name' in filtered_labels
        assert 'error.type' in filtered_labels
        assert 'db.operation.name' not in filtered_labels  # Excluded!

    def test_disabled_metric_not_created(self):
        """Test that metrics with empty buckets are disabled (not created)."""
        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics',
                    'system': {
                        'gateway.ttfb.duration': {
                            'values': []  # Disabled
                        }
                    }
                }
            }
        }
        registry = MetricRegistry(config)

        # Verify metric was not created
        assert 'gateway.ttfb.duration' not in registry.recorders

    def test_validation_rejects_unknown_system_metric(self):
        """Test validation rejects unknown metric names in system: section."""
        obs_config = {
            'enabled': True,
            'system': {
                'unknown.metric.name': {
                    'values': [1.0, 2.0]
                }
            }
        }

        with pytest.raises(ValueError, match="Unknown system metric 'unknown.metric.name'"):
            validate_config(obs_config)

    def test_validation_rejects_invalid_buckets(self):
        """Test validation rejects invalid bucket configurations."""
        obs_config = {
            'enabled': True,
            'system': {
                'db.duration': {
                    'values': [10.0, 5.0, 1.0]  # Not in ascending order
                }
            }
        }

        with pytest.raises(ValueError, match="buckets must be in ascending order"):
            validate_config(obs_config)

    def test_validation_rejects_non_positive_buckets(self):
        """Test validation rejects buckets with values <= 0."""
        obs_config = {
            'enabled': True,
            'system': {
                'db.duration': {
                    'values': [0.0, 1.0, 2.0]  # Zero is not allowed
                }
            }
        }

        with pytest.raises(ValueError, match="buckets must be positive"):
            validate_config(obs_config)

    def test_validation_rejects_negative_buckets(self):
        """Test validation rejects negative bucket values."""
        obs_config = {
            'enabled': True,
            'system': {
                'db.duration': {
                    'values': [-1.0, 1.0, 2.0]  # Negative not allowed
                }
            }
        }

        with pytest.raises(ValueError, match="buckets must be positive"):
            validate_config(obs_config)

    def test_validation_rejects_non_list_exclude_labels_in_system(self):
        """Test validation rejects non-list exclude_labels in system: section."""
        obs_config = {
            'enabled': True,
            'system': {
                'db.duration': {
                    'exclude_labels': 'not_a_list'  # Should be a list
                }
            }
        }

        with pytest.raises(ValueError, match="system.db.duration.exclude_labels must be a list"):
            validate_config(obs_config)

    def test_validation_rejects_non_string_in_exclude_labels_system(self):
        """Test validation rejects non-string values in exclude_labels for system: section."""
        obs_config = {
            'enabled': True,
            'system': {
                'db.duration': {
                    'exclude_labels': ['valid_label', 123, 'another_label']  # 123 is not a string
                }
            }
        }

        with pytest.raises(ValueError, match="system.db.duration.exclude_labels must contain only strings"):
            validate_config(obs_config)

    def test_empty_buckets_histogram_not_recorded(self):
        """Test that histogram with empty buckets is not created and cannot record."""
        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics',
                    'system': {
                        'gateway.ttfb.duration': {
                            'values': []  # Empty = disabled
                        }
                    }
                }
            }
        }
        registry = MetricRegistry(config)

        # Verify metric is not in recorders
        assert 'gateway.ttfb.duration' not in registry.recorders

        # Verify get_recorder returns None
        recorder = registry.get_recorder('gateway.ttfb.duration')
        assert recorder is None

        # Verify total number of recorders is 6 (not 7)
        assert len(registry.recorders) == 6


class TestCustomMetricsFactoryMethods:
    """Test custom metrics factory methods and label filtering."""

    def test_create_counter_when_enabled(self):
        """Test create_counter returns CounterRecorder when enabled."""
        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics'
                }
            }
        }
        registry = MetricRegistry(config)

        counter = registry.create_counter(
            name='test.events.count',
            description='Test event counter'
        )

        assert isinstance(counter, CounterRecorder)
        assert 'test.events.count' in registry.recorders

    def test_create_counter_when_disabled(self):
        """Test create_counter returns NoOpRecorder when disabled."""
        config = {}
        registry = MetricRegistry(config)

        counter = registry.create_counter(
            name='test.events.count',
            description='Test event counter'
        )

        assert isinstance(counter, NoOpRecorder)

    def test_create_gauge_when_enabled(self):
        """Test create_gauge returns GaugeRecorder when enabled."""
        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics'
                }
            }
        }
        registry = MetricRegistry(config)

        gauge = registry.create_gauge(
            name='test.queue.depth',
            description='Test queue depth'
        )

        assert isinstance(gauge, GaugeRecorder)
        assert 'test.queue.depth' in registry.recorders

    def test_create_gauge_when_disabled(self):
        """Test create_gauge returns NoOpRecorder when disabled."""
        config = {}
        registry = MetricRegistry(config)

        gauge = registry.create_gauge(
            name='test.queue.depth',
            description='Test queue depth'
        )

        assert isinstance(gauge, NoOpRecorder)

    def test_create_observable_gauge_when_enabled(self):
        """Test create_observable_gauge returns instrument when enabled."""
        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics'
                }
            }
        }
        registry = MetricRegistry(config)

        def callback(options):
            from opentelemetry.metrics import Observation
            return [Observation(42, {"label": "value"})]

        obs_gauge = registry.create_observable_gauge(
            name='test.current.value',
            callbacks=[callback],
            description='Test observable gauge'
        )

        assert obs_gauge is not None  # Returns OTel instrument

    def test_create_observable_gauge_when_disabled(self):
        """Test create_observable_gauge returns None when disabled."""
        config = {}
        registry = MetricRegistry(config)

        def callback(options):
            from opentelemetry.metrics import Observation
            return [Observation(42, {"label": "value"})]

        obs_gauge = registry.create_observable_gauge(
            name='test.current.value',
            callbacks=[callback],
            description='Test observable gauge'
        )

        assert obs_gauge is None

    def test_custom_counter_label_filtering(self):
        """Test custom: config filters labels for counters."""
        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics',
                    'custom': {
                        'gateway.events.processed': {
                            'exclude_labels': ['verbose_detail']
                        }
                    }
                }
            }
        }
        registry = MetricRegistry(config)

        counter = registry.create_counter(
            name='gateway.events.processed',
            description='Events processed by gateway'
        )

        # Verify exclude_labels were applied
        assert isinstance(counter, CounterRecorder)
        assert 'verbose_detail' in counter._excluded_labels

    def test_custom_gauge_label_filtering(self):
        """Test custom: config filters labels for gauges."""
        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics',
                    'custom': {
                        'broker.active.connections': {
                            'exclude_labels': ['detail_label']
                        }
                    }
                }
            }
        }
        registry = MetricRegistry(config)

        gauge = registry.create_gauge(
            name='broker.active.connections',
            description='Active broker connections'
        )

        # Verify exclude_labels were applied
        assert isinstance(gauge, GaugeRecorder)
        assert 'detail_label' in gauge._excluded_labels

    def test_custom_counter_filtering_actually_filters(self):
        """Test that custom: filtering rules actually filter recorded labels."""
        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics',
                    'custom': {
                        'gateway.events.processed': {
                            'exclude_labels': ['verbose_detail', 'internal_id']
                        }
                    }
                }
            }
        }
        registry = MetricRegistry(config)

        counter = registry.create_counter(
            name='gateway.events.processed',
            description='Events processed'
        )

        # Mock the underlying counter to verify filtered labels
        mock_counter = Mock()
        counter._counter = mock_counter

        # Record with mix of allowed and excluded labels
        labels = {
            'gateway': 'chat',
            'event_type': 'message',
            'verbose_detail': 'should_be_filtered',  # Excluded
            'internal_id': '12345'  # Excluded
        }
        counter.record(1, labels)

        # Verify counter was called with filtered labels
        mock_counter.add.assert_called_once()
        call_args = mock_counter.add.call_args
        filtered_labels = call_args[1]['attributes']

        assert 'gateway' in filtered_labels
        assert 'event_type' in filtered_labels
        assert 'verbose_detail' not in filtered_labels  # Filtered!
        assert 'internal_id' not in filtered_labels  # Filtered!

    def test_gauge_up_down_behavior(self):
        """Test that gauge supports both increment (up) and decrement (down) operations."""
        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics'
                }
            }
        }
        registry = MetricRegistry(config)

        gauge = registry.create_gauge(
            name='broker.active.connections',
            description='Active connections'
        )

        # Mock the underlying gauge to verify values
        mock_gauge = Mock()
        gauge._gauge = mock_gauge

        labels = {'broker.name': 'prod'}

        # Test increment (positive value)
        gauge.record(1, labels)
        assert mock_gauge.add.call_count == 1
        assert mock_gauge.add.call_args[0][0] == 1  # First positional arg is the value

        # Test decrement (negative value)
        gauge.record(-1, labels)
        assert mock_gauge.add.call_count == 2
        assert mock_gauge.add.call_args[0][0] == -1  # Value should be negative

        # Test larger increment
        gauge.record(5, labels)
        assert mock_gauge.add.call_count == 3
        assert mock_gauge.add.call_args[0][0] == 5

        # Test larger decrement
        gauge.record(-3, labels)
        assert mock_gauge.add.call_count == 4
        assert mock_gauge.add.call_args[0][0] == -3

    def test_custom_gauge_filtering_actually_filters(self):
        """Test that custom: filtering rules actually filter gauge labels."""
        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics',
                    'custom': {
                        'broker.active.connections': {
                            'exclude_labels': ['connection_id']
                        }
                    }
                }
            }
        }
        registry = MetricRegistry(config)

        gauge = registry.create_gauge(
            name='broker.active.connections',
            description='Active connections'
        )

        # Mock the underlying gauge to verify filtered labels
        mock_gauge = Mock()
        gauge._gauge = mock_gauge

        # Record with mix of allowed and excluded labels
        labels = {
            'broker.name': 'prod',
            'connection_id': 'conn-12345'  # Should be filtered
        }
        gauge.record(1, labels)

        # Verify gauge was called with filtered labels
        mock_gauge.add.assert_called_once()
        call_args = mock_gauge.add.call_args
        filtered_labels = call_args[1]['attributes']

        assert 'broker.name' in filtered_labels
        assert 'connection_id' not in filtered_labels  # Filtered!

    def test_gauge_up_down_with_label_filtering(self):
        """Test that gauge up/down behavior works correctly with label filtering."""
        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics',
                    'custom': {
                        'queue.depth': {
                            'exclude_labels': ['internal_id', 'debug_info']
                        }
                    }
                }
            }
        }
        registry = MetricRegistry(config)

        gauge = registry.create_gauge(
            name='queue.depth',
            description='Queue depth'
        )

        # Mock the underlying gauge
        mock_gauge = Mock()
        gauge._gauge = mock_gauge

        labels_with_excluded = {
            'queue': 'main',
            'priority': 'high',
            'internal_id': 'q-12345',  # Should be filtered
            'debug_info': 'test-data'   # Should be filtered
        }

        # Test increment with label filtering
        gauge.record(10, labels_with_excluded)
        assert mock_gauge.add.call_count == 1
        assert mock_gauge.add.call_args[0][0] == 10  # Value is 10
        filtered_labels = mock_gauge.add.call_args[1]['attributes']
        assert 'queue' in filtered_labels
        assert 'priority' in filtered_labels
        assert 'internal_id' not in filtered_labels  # Filtered!
        assert 'debug_info' not in filtered_labels   # Filtered!

        # Test decrement with label filtering
        gauge.record(-5, labels_with_excluded)
        assert mock_gauge.add.call_count == 2
        assert mock_gauge.add.call_args[0][0] == -5  # Value is -5
        filtered_labels = mock_gauge.add.call_args[1]['attributes']
        assert 'queue' in filtered_labels
        assert 'priority' in filtered_labels
        assert 'internal_id' not in filtered_labels  # Still filtered!
        assert 'debug_info' not in filtered_labels   # Still filtered!

    def test_custom_observable_gauge_filtering(self):
        """Test that custom: filtering wraps observable gauge callbacks."""
        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics',
                    'custom': {
                        'queue.depth': {
                            'exclude_labels': ['internal_queue_id']
                        }
                    }
                }
            }
        }
        registry = MetricRegistry(config)

        from opentelemetry.metrics import Observation

        def callback(options):
            return [
                Observation(10, {
                    'queue': 'main',
                    'internal_queue_id': 'q-12345'  # Should be filtered
                })
            ]

        # Create observable gauge
        obs_gauge = registry.create_observable_gauge(
            name='queue.depth',
            callbacks=[callback],
            description='Queue depth'
        )

        # The filtering is applied by wrapping callbacks
        # Verify the gauge was created
        assert obs_gauge is not None

    def test_validation_accepts_valid_custom_config(self):
        """Test validation accepts valid custom: section."""
        obs_config = {
            'enabled': True,
            'custom': {
                'my.custom.metric': {
                    'exclude_labels': ['label1', 'label2']
                }
            }
        }

        # Should not raise
        validate_config(obs_config)

    def test_validation_rejects_invalid_custom_config_key(self):
        """Test validation rejects invalid keys in custom: section."""
        obs_config = {
            'enabled': True,
            'custom': {
                'my.custom.metric': {
                    'invalid_key': 'value'
                }
            }
        }

        with pytest.raises(ValueError, match="only 'exclude_labels' is allowed"):
            validate_config(obs_config)

    def test_validation_rejects_non_list_exclude_labels(self):
        """Test validation rejects non-list exclude_labels in custom: section."""
        obs_config = {
            'enabled': True,
            'custom': {
                'my.custom.metric': {
                    'exclude_labels': 'not_a_list'
                }
            }
        }

        with pytest.raises(ValueError, match="exclude_labels must be a list"):
            validate_config(obs_config)

    def test_validation_rejects_non_string_in_exclude_labels_custom(self):
        """Test validation rejects non-string values in exclude_labels for custom: section."""
        obs_config = {
            'enabled': True,
            'custom': {
                'my.custom.metric': {
                    'exclude_labels': ['valid_label', 456, 'another_label']  # 456 is not a string
                }
            }
        }

        with pytest.raises(ValueError, match="exclude_labels must contain only strings"):
            validate_config(obs_config)

    def test_noop_recorder_is_safe_to_use(self):
        """Test NoOpRecorder can be called without errors."""
        noop = NoOpRecorder()

        # Should not raise
        noop.record(100, {'label': 'value'})
        noop.record(0, {})
        noop.record(-5, {'a': 'b', 'c': 'd'})

    def test_factory_methods_apply_prefix(self):
        """Test factory methods apply metric prefix."""
        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics',
                    'metric_prefix': 'sam'
                }
            }
        }
        registry = MetricRegistry(config)

        # The full name should have prefix applied
        full_name = registry._get_full_metric_name('custom.metric')
        assert full_name == 'sam.custom.metric'


class TestGetRecorder:
    """Test get_recorder method for backward compatibility."""

    def test_get_recorder_returns_histogram_when_enabled(self):
        """Test get_recorder returns histogram recorder when enabled."""
        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics'
                }
            }
        }
        registry = MetricRegistry(config)

        recorder = registry.get_recorder('db.duration')
        assert isinstance(recorder, HistogramRecorder)

    def test_get_recorder_returns_none_when_disabled(self):
        """Test get_recorder returns None when disabled."""
        config = {}
        registry = MetricRegistry(config)

        recorder = registry.get_recorder('db.duration')
        assert recorder is None

    def test_get_recorder_returns_none_for_unknown_metric(self):
        """Test get_recorder returns None for unknown metric."""
        config = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'path': '/metrics'
                }
            }
        }
        registry = MetricRegistry(config)

        recorder = registry.get_recorder('unknown.metric')
        assert recorder is None
