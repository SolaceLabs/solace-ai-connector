"""Test all observability APIs work safely when MetricRegistry is not explicitly initialized.

This validates the defensive auto-initialization behavior - instrumented code should
never fail even when observability is not explicitly set up.
"""

import pytest

from solace_ai_connector.common.observability.registry import MetricRegistry
from solace_ai_connector.common.observability import (
    MonitorLatency,
    BrokerMonitor,
    GenAIMonitor,
    GenAITTFTMonitor,
    GenAITokenMonitor,
    GenAICostMonitor,
    DBMonitor,
    OperationMonitor,
)


class TestObservabilityWithoutExplicitInitialization:
    """Test all observability APIs when MetricRegistry NOT explicitly initialized."""

    def test_get_instance_auto_initializes(self):

        MetricRegistry.reset()

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
        """Test explicit initialization overrides auto-initialization."""
        MetricRegistry.reset()

        # Step 1: Instrumented code calls get_instance() early (auto-init)
        auto_instance = MetricRegistry.get_instance()
        assert auto_instance.enabled is False
        assert auto_instance._explicitly_initialized is False

        # Step 2: Application startup calls initialize() with real config
        # This should OVERRIDE the auto-initialized instance (not raise)
        config = {
            'management_server': {
                'observability': {
                    'enabled': True
                }
            }
        }
        explicit_instance = MetricRegistry.initialize(config)

        # Should have created a NEW instance with enabled observability
        assert explicit_instance.enabled is True
        assert explicit_instance._explicitly_initialized is True
        assert explicit_instance is not auto_instance

        # Subsequent get_instance() calls should return the explicit instance
        assert MetricRegistry.get_instance() is explicit_instance

    def test_initialize_does_not_override_explicit_init(self):
        """Test that initialize() raises when trying to override explicit initialization."""
        MetricRegistry.reset()

        # Explicitly initialize with config A
        config_a = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'metric_prefix': 'app_a'
                }
            }
        }
        instance_a = MetricRegistry.initialize(config_a)
        assert instance_a._explicitly_initialized is True

        # Try to initialize with different config B - should raise
        config_b = {
            'management_server': {
                'observability': {
                    'enabled': True,
                    'metric_prefix': 'app_b'  # Different!
                }
            }
        }

        with pytest.raises(RuntimeError, match="already initialized with different config"):
            MetricRegistry.initialize(config_b)

    def test_thread_safety_get_instance(self):
        """Test get_instance() is thread-safe - no duplicate instances."""
        import threading

        MetricRegistry.reset()

        instances = []
        errors = []

        def get_instance_in_thread():
            try:
                instance = MetricRegistry.get_instance()
                instances.append(instance)
            except Exception as e:
                errors.append(e)

        # Launch 10 threads simultaneously
        threads = [threading.Thread(target=get_instance_in_thread) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No errors should occur
        assert len(errors) == 0

        # All threads should get the SAME instance
        assert len(instances) == 10
        first_instance = instances[0]
        assert all(inst is first_instance for inst in instances)

    def test_thread_safety_initialize(self):
        """Test initialize() is thread-safe - no duplicate instances."""
        import threading

        MetricRegistry.reset()

        config = {
            'management_server': {
                'observability': {
                    'enabled': True
                }
            }
        }

        instances = []
        errors = []

        def initialize_in_thread():
            try:
                instance = MetricRegistry.initialize(config)
                instances.append(instance)
            except Exception as e:
                errors.append(e)

        # Launch 10 threads simultaneously
        threads = [threading.Thread(target=initialize_in_thread) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No errors should occur
        assert len(errors) == 0

        # All threads should get the SAME instance
        assert len(instances) == 10
        first_instance = instances[0]
        assert all(inst is first_instance for inst in instances)

    def test_thread_safety_mixed_get_and_initialize(self):
        """Test mixed get_instance() and initialize() calls are thread-safe."""
        import threading
        import random

        MetricRegistry.reset()

        config = {
            'management_server': {
                'observability': {
                    'enabled': True
                }
            }
        }

        instances = []
        errors = []

        def random_access():
            try:
                # Randomly call get_instance() or initialize()
                if random.choice([True, False]):
                    instance = MetricRegistry.get_instance()
                else:
                    instance = MetricRegistry.initialize(config)
                instances.append(instance)
            except Exception as e:
                errors.append(e)

        # Launch 20 threads with mixed calls
        threads = [threading.Thread(target=random_access) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No errors should occur
        assert len(errors) == 0

        # All should eventually get same explicitly initialized instance
        final_instance = MetricRegistry.get_instance()
        assert final_instance._explicitly_initialized is True
        assert final_instance.enabled is True
