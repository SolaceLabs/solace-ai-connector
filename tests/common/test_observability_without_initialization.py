"""Test all observability APIs work safely when MetricRegistry is not explicitly initialized.

This validates the defensive auto-initialization behavior - instrumented code should
never fail even when observability is not explicitly set up.
"""

import pytest
from unittest.mock import Mock

from solace_ai_connector.common.observability.registry import MetricRegistry
from solace_ai_connector.common.observability import (
    MonitorLatency,
    BrokerMonitor,
    GenAIMonitor,
    GenAITTFTMonitor,
    GenAITokenMonitor,
    GenAICostMonitor,
    DBMonitor,
    GatewayMonitor,
    GatewayTTFBMonitor,
    OperationMonitor,
)


class TestObservabilityWithoutExplicitInitialization:
    """Test all observability APIs when MetricRegistry NOT explicitly initialized."""

    def test_get_instance_auto_initializes(self):
        """Test get_instance() auto-initializes with disabled observability."""
        MetricRegistry.reset()

        # get_instance() should not raise - should auto-initialize
        registry = MetricRegistry.get_instance()

        assert registry is not None
        assert registry.enabled is False
        assert registry.duration_recorders == {}
        assert registry._value_recorders == {}

    def test_broker_monitor_without_initialization(self):
        """Test BrokerMonitor works when registry not initialized."""
        MetricRegistry.reset()

        # Should not raise - becomes no-op
        with MonitorLatency(BrokerMonitor.publish()):
            pass

    def test_genai_monitor_without_initialization(self):
        """Test GenAIMonitor works when registry not initialized."""
        MetricRegistry.reset()

        monitor = GenAIMonitor.create(model="gpt-4")

        with MonitorLatency(monitor):
            pass

    def test_genai_ttft_monitor_without_initialization(self):
        """Test GenAITTFTMonitor works when registry not initialized."""
        MetricRegistry.reset()

        monitor = GenAITTFTMonitor.create(model="gpt-4")

        with MonitorLatency(monitor):
            pass

    def test_genai_token_monitor_without_initialization(self):
        """Test GenAITokenMonitor works when registry not initialized."""
        MetricRegistry.reset()

        monitor = GenAITokenMonitor.create(
            model="gpt-4",
            component_name="test-agent",
            owner_id="test-user",
            token_type="input"
        )

        assert monitor is not None
        assert monitor.monitor_type == "gen_ai.tokens.used"

    def test_genai_cost_monitor_without_initialization(self):
        """Test GenAICostMonitor works when registry not initialized."""
        MetricRegistry.reset()

        monitor = GenAICostMonitor.create(
            model="gpt-4",
            component_name="test-agent",
            owner_id="test-user"
        )

        assert monitor is not None
        assert monitor.monitor_type == "gen_ai.cost.total"

    def test_db_monitor_without_initialization(self):
        """Test DBMonitor works when registry not initialized."""
        MetricRegistry.reset()

        monitor = DBMonitor.query("users")

        with MonitorLatency(monitor):
            pass

    # Gateway monitors are abstract - no factory methods
    # Skip testing them directly

    def test_operation_monitor_without_initialization(self):
        """Test OperationMonitor works when registry not initialized."""
        MetricRegistry.reset()

        monitor = OperationMonitor.create(
            component_type="processor",
            component_name="transformer-1",
            operation="transform"
        )

        with MonitorLatency(monitor):
            pass

    def test_monitor_latency_with_exception_no_initialization(self):
        """Test MonitorLatency handles exceptions when registry not initialized."""
        MetricRegistry.reset()

        # Should not raise RuntimeError - exception should propagate normally
        with pytest.raises(ValueError):
            with MonitorLatency(BrokerMonitor.publish()):
                raise ValueError("Test error")

    def test_monitor_latency_async_without_initialization(self):
        """Test async MonitorLatency works when registry not initialized."""
        import asyncio

        MetricRegistry.reset()

        async def async_operation():
            async with MonitorLatency(BrokerMonitor.publish()):
                await asyncio.sleep(0.001)
                return "result"

        result = asyncio.run(async_operation())
        assert result == "result"

    def test_monitor_latency_decorator_sync_without_initialization(self):
        """Test MonitorLatency as decorator on sync function when registry not initialized."""
        MetricRegistry.reset()

        @MonitorLatency(BrokerMonitor.publish())
        def sync_function():
            return "result"

        result = sync_function()
        assert result == "result"

    def test_monitor_latency_decorator_async_without_initialization(self):
        """Test MonitorLatency as decorator on async function when registry not initialized."""
        import asyncio

        MetricRegistry.reset()

        @MonitorLatency(BrokerMonitor.publish())
        async def async_function():
            return "result"

        result = asyncio.run(async_function())
        assert result == "result"

    def test_monitor_latency_manual_start_stop_without_initialization(self):
        """Test manual start/stop when registry not initialized."""
        MetricRegistry.reset()

        monitor = MonitorLatency(BrokerMonitor.publish())
        monitor.start()
        monitor.stop()

    def test_monitor_latency_manual_error_without_initialization(self):
        """Test manual error recording when registry not initialized."""
        MetricRegistry.reset()

        monitor = MonitorLatency(BrokerMonitor.publish())
        monitor.start()

        try:
            raise ValueError("Test error")
        except ValueError as e:
            monitor.error(e)

    def test_all_monitors_in_sequence_without_initialization(self):
        """Test using multiple monitors sequentially when registry not initialized."""
        MetricRegistry.reset()

        # All of these should work without raising
        with MonitorLatency(BrokerMonitor.publish()):
            pass

        with MonitorLatency(GenAIMonitor.create("gpt-4")):
            pass

        with MonitorLatency(DBMonitor.query("users")):
            pass

        with MonitorLatency(OperationMonitor.create("processor", "comp-1", "process")):
            pass

    def test_nested_monitors_without_initialization(self):
        """Test nested MonitorLatency contexts when registry not initialized."""
        MetricRegistry.reset()

        with MonitorLatency(OperationMonitor.create("processor", "comp-1", "outer")):
            with MonitorLatency(DBMonitor.query("users")):
                with MonitorLatency(GenAIMonitor.create("gpt-4")):
                    pass

    def test_registry_create_counter_without_initialization(self):
        """Test registry.create_counter() works when not initialized."""
        MetricRegistry.reset()

        registry = MetricRegistry.get_instance()
        counter = registry.create_counter("test.counter", "Test counter")

        # Should return NoOpRecorder since auto-initialized disabled
        from solace_ai_connector.common.observability.recorders import NoOpRecorder
        assert isinstance(counter, NoOpRecorder)

        # Should not raise
        counter.record(1, {"label": "value"})

    def test_registry_create_gauge_without_initialization(self):
        """Test registry.create_gauge() works when not initialized."""
        MetricRegistry.reset()

        registry = MetricRegistry.get_instance()
        gauge = registry.create_gauge("test.gauge", "Test gauge")

        # Should return NoOpRecorder since auto-initialized disabled
        from solace_ai_connector.common.observability.recorders import NoOpRecorder
        assert isinstance(gauge, NoOpRecorder)

        # Should not raise
        gauge.record(42, {"label": "value"})

    def test_registry_create_observable_gauge_without_initialization(self):
        """Test registry.create_observable_gauge() works when not initialized."""
        MetricRegistry.reset()

        registry = MetricRegistry.get_instance()

        def callback(options):
            from opentelemetry.metrics import Observation
            return [Observation(10, {"queue": "main"})]

        # Should return NoOpObservableGauge (not None) for consistency
        result = registry.create_observable_gauge(
            "test.observable",
            [callback],
            "Test observable gauge"
        )

        from solace_ai_connector.common.observability.recorders import NoOpObservableGauge
        assert isinstance(result, NoOpObservableGauge)

    def test_registry_get_recorder_without_initialization(self):
        """Test registry.get_recorder() works when not initialized."""
        MetricRegistry.reset()

        registry = MetricRegistry.get_instance()
        recorder = registry.get_recorder("gen_ai.client.operation.duration")

        # Should return None since auto-initialized disabled
        assert recorder is None

    def test_all_monitor_factory_methods_without_initialization(self):
        """Test all monitor factory methods work when registry not initialized."""
        MetricRegistry.reset()

        # All factory methods should succeed
        monitors = [
            BrokerMonitor.publish(),
            GenAIMonitor.create("gpt-4"),
            GenAITTFTMonitor.create("gpt-4"),
            GenAITokenMonitor.create("gpt-4", "agent", "user", "input"),
            GenAICostMonitor.create("gpt-4", "agent", "user"),
            DBMonitor.query("users"),
            DBMonitor.insert("users"),
            DBMonitor.update("users"),
            DBMonitor.delete("users"),
            OperationMonitor.create("processor", "comp-1", "transform"),
        ]

        # All should be MonitorInstance objects
        for monitor in monitors:
            assert monitor is not None
            assert hasattr(monitor, 'monitor_type')
            assert hasattr(monitor, 'labels')

    def test_get_instance_singleton_behavior(self):
        """Test get_instance() returns same instance across calls."""
        MetricRegistry.reset()

        instance1 = MetricRegistry.get_instance()
        instance2 = MetricRegistry.get_instance()

        assert instance1 is instance2

    def test_explicit_initialization_after_auto_init(self):
        """Test explicit initialization works after auto-initialization."""
        MetricRegistry.reset()

        # Auto-initialize (disabled)
        auto_instance = MetricRegistry.get_instance()
        assert auto_instance.enabled is False

        # Reset and explicitly initialize with enabled
        MetricRegistry.reset()
        config = {
            'management_server': {
                'observability': {
                    'enabled': True
                }
            }
        }
        explicit_instance = MetricRegistry.initialize(config)

        assert explicit_instance.enabled is True
        assert explicit_instance is not auto_instance