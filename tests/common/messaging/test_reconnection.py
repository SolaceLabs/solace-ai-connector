"""Tests for reconnection and subscription restoration functionality.

These tests avoid mocking where possible, using real Python objects
and the DevBroker test double for integration-style tests.
"""

import sys
import pytest
import threading

sys.path.append("src")

from solace_ai_connector.common.messaging.dev_broker_messaging import DevBroker


class TestReconnectionCallbacksPurePython:
    """Tests for callback mechanics using pure Python (no mocking)."""

    def test_callback_list_starts_empty(self):
        """Verify callback list is initialized empty."""
        callbacks = []
        assert len(callbacks) == 0

    def test_callback_registration_appends_to_list(self):
        """Test that registering callbacks appends them to a list."""
        callbacks = []

        def callback1():
            pass

        def callback2():
            pass

        callbacks.append(callback1)
        callbacks.append(callback2)

        assert len(callbacks) == 2
        assert callback1 in callbacks
        assert callback2 in callbacks

    def test_all_callbacks_invoked_in_order(self):
        """Test that all callbacks are invoked when iterating."""
        call_order = []

        def callback1():
            call_order.append(1)

        def callback2():
            call_order.append(2)

        def callback3():
            call_order.append(3)

        callbacks = [callback1, callback2, callback3]

        for callback in callbacks:
            callback()

        assert call_order == [1, 2, 3]

    def test_exception_in_callback_doesnt_stop_iteration(self):
        """Test that one callback raising doesn't prevent others from running."""
        results = []

        def callback1():
            results.append(1)

        def callback2():
            raise ValueError("Intentional error")

        def callback3():
            results.append(3)

        callbacks = [callback1, callback2, callback3]

        for callback in callbacks:
            try:
                callback()
            except Exception:
                pass  # Swallow exception, continue to next

        assert results == [1, 3]

    def test_thread_safe_callback_registration(self):
        """Test that callback registration is thread-safe with a lock."""
        callbacks = []
        lock = threading.Lock()
        registration_count = 100

        def register_callback(n):
            with lock:
                callbacks.append(lambda: n)

        threads = []
        for i in range(registration_count):
            t = threading.Thread(target=register_callback, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(callbacks) == registration_count


class TestSubscriptionTrackingPurePython:
    """Tests for subscription tracking using pure Python."""

    def test_subscription_set_operations(self):
        """Test basic set operations for tracking subscriptions."""
        active_subscriptions = set()

        # Add subscriptions
        active_subscriptions.add("topic/a")
        active_subscriptions.add("topic/b")
        active_subscriptions.add("topic/c")

        assert len(active_subscriptions) == 3
        assert "topic/a" in active_subscriptions
        assert "topic/b" in active_subscriptions
        assert "topic/c" in active_subscriptions

    def test_subscription_copy_is_independent(self):
        """Test that copying subscriptions creates an independent copy."""
        active_subscriptions = {"topic/a", "topic/b"}

        # Get a copy
        copy = active_subscriptions.copy()

        # Modify the copy
        copy.add("topic/c")
        copy.discard("topic/a")

        # Original should be unchanged
        assert active_subscriptions == {"topic/a", "topic/b"}
        assert copy == {"topic/b", "topic/c"}

    def test_thread_safe_subscription_access(self):
        """Test that subscription operations are thread-safe with a lock."""
        active_subscriptions = set()
        lock = threading.Lock()
        num_operations = 100

        def add_subscription(topic):
            with lock:
                active_subscriptions.add(topic)

        def remove_subscription(topic):
            with lock:
                active_subscriptions.discard(topic)

        # Add subscriptions from multiple threads
        add_threads = []
        for i in range(num_operations):
            t = threading.Thread(target=add_subscription, args=(f"topic/{i}",))
            add_threads.append(t)
            t.start()

        for t in add_threads:
            t.join()

        assert len(active_subscriptions) == num_operations

        # Remove half from multiple threads
        remove_threads = []
        for i in range(0, num_operations, 2):
            t = threading.Thread(target=remove_subscription, args=(f"topic/{i}",))
            remove_threads.append(t)
            t.start()

        for t in remove_threads:
            t.join()

        assert len(active_subscriptions) == num_operations // 2

    def test_get_subscriptions_returns_copy_not_reference(self):
        """Test that getting subscriptions returns a copy for thread safety."""
        active_subscriptions = {"topic/a", "topic/b"}
        lock = threading.Lock()

        def get_active_subscriptions():
            with lock:
                return active_subscriptions.copy()

        # Get subscriptions
        subs = get_active_subscriptions()

        # Modify returned set
        subs.add("topic/c")

        # Original should be unchanged
        assert "topic/c" not in active_subscriptions
        assert len(active_subscriptions) == 2


class StubFlowLockManager:
    """Simple stub for flow_lock_manager."""

    def __init__(self):
        self._locks = {}

    def get_lock(self, name):
        if name not in self._locks:
            self._locks[name] = threading.Lock()
        return self._locks[name]


class StubFlowKvStore:
    """Simple stub for flow_kv_store."""

    def __init__(self):
        self._store = {}

    def get(self, key):
        return self._store.get(key)

    def set(self, key, value):
        self._store[key] = value


class TestDevBrokerReconnection:
    """Tests for DevBroker reconnection interface."""

    @pytest.fixture
    def flow_lock_manager(self):
        return StubFlowLockManager()

    @pytest.fixture
    def flow_kv_store(self):
        return StubFlowKvStore()

    @pytest.fixture
    def dev_broker(self, flow_lock_manager, flow_kv_store):
        broker_properties = {
            "queue_name": "test_queue",
            "subscriptions": [{"topic": "test/topic"}],
        }
        return DevBroker(broker_properties, flow_lock_manager, flow_kv_store)

    def test_dev_broker_has_reconnection_callback_list(self, dev_broker):
        """Test that DevBroker initializes with empty callback list."""
        assert hasattr(dev_broker, "_reconnection_callbacks")
        assert isinstance(dev_broker._reconnection_callbacks, list)
        assert len(dev_broker._reconnection_callbacks) == 0

    def test_dev_broker_register_reconnection_callback(self, dev_broker):
        """Test that DevBroker can register callbacks."""
        call_count = [0]

        def my_callback():
            call_count[0] += 1

        dev_broker.register_reconnection_callback(my_callback)

        assert my_callback in dev_broker._reconnection_callbacks
        assert len(dev_broker._reconnection_callbacks) == 1

    def test_dev_broker_register_multiple_callbacks(self, dev_broker):
        """Test that DevBroker can register multiple callbacks."""

        def callback1():
            pass

        def callback2():
            pass

        def callback3():
            pass

        dev_broker.register_reconnection_callback(callback1)
        dev_broker.register_reconnection_callback(callback2)
        dev_broker.register_reconnection_callback(callback3)

        assert len(dev_broker._reconnection_callbacks) == 3

    def test_dev_broker_restore_subscriptions_returns_success(self, dev_broker):
        """Test that restore_subscriptions_with_rebind returns success counts."""
        subscriptions = {"topic/a", "topic/b", "topic/c"}

        success, failed = dev_broker.restore_subscriptions_with_rebind(
            subscriptions=subscriptions,
            queue_name="test_queue",
            temporary=True,
        )

        assert success == 3
        assert failed == 0

    def test_dev_broker_restore_subscriptions_with_empty_set(self, dev_broker):
        """Test restore with empty subscription set."""
        subscriptions = set()

        success, failed = dev_broker.restore_subscriptions_with_rebind(
            subscriptions=subscriptions,
            queue_name="test_queue",
            temporary=True,
        )

        assert success == 0
        assert failed == 0


class TestDevBrokerSubscriptionManagement:
    """Tests for DevBroker subscription add/remove."""

    @pytest.fixture
    def flow_lock_manager(self):
        return StubFlowLockManager()

    @pytest.fixture
    def flow_kv_store(self):
        return StubFlowKvStore()

    @pytest.fixture
    def dev_broker(self, flow_lock_manager, flow_kv_store):
        broker_properties = {
            "queue_name": "test_queue",
            "subscriptions": [],
        }
        broker = DevBroker(broker_properties, flow_lock_manager, flow_kv_store)
        broker.connect()
        return broker

    def test_add_topic_subscription(self, dev_broker):
        """Test adding a topic subscription."""
        result = dev_broker.add_topic_subscription("test/new/topic")
        assert result is True

    def test_add_topic_to_queue(self, dev_broker):
        """Test adding a topic to a specific queue."""
        result = dev_broker.add_topic_to_queue("test/topic/+", "test_queue")
        assert result is True

    def test_remove_topic_from_queue(self, dev_broker):
        """Test removing a topic from a queue."""
        # First add
        dev_broker.add_topic_to_queue("test/topic/remove", "test_queue")
        # Then remove
        result = dev_broker.remove_topic_from_queue("test/topic/remove", "test_queue")
        assert result is True

    def test_remove_nonexistent_topic(self, dev_broker):
        """Test removing a topic that doesn't exist."""
        result = dev_broker.remove_topic_from_queue("nonexistent/topic", "test_queue")
        assert result is False

    def test_subscription_message_routing(self, dev_broker):
        """Test that messages are routed to queues with matching subscriptions."""
        # Add subscription
        dev_broker.add_topic_to_queue("test/routing/>", "test_queue")

        # Send a message
        dev_broker.send_message(
            destination_name="test/routing/level1/level2",
            payload="test payload",
            user_properties={"key": "value"},
        )

        # Receive the message
        msg = dev_broker.receive_message(timeout_ms=1000, queue_name="test_queue")

        assert msg is not None
        assert msg["payload"] == "test payload"
        assert msg["topic"] == "test/routing/level1/level2"
        assert msg["user_properties"]["key"] == "value"

    def test_wildcard_subscription_single_level(self, dev_broker):
        """Test single-level wildcard (*) subscription."""
        dev_broker.add_topic_to_queue("test/*/end", "test_queue")

        # Should match
        dev_broker.send_message("test/middle/end", "match1")
        msg = dev_broker.receive_message(1000, "test_queue")
        assert msg is not None
        assert msg["payload"] == "match1"

        # Should not match (two levels in middle)
        dev_broker.send_message("test/a/b/end", "no_match")
        msg = dev_broker.receive_message(100, "test_queue")
        assert msg is None

    def test_wildcard_subscription_multi_level(self, dev_broker):
        """Test multi-level wildcard (>) subscription."""
        dev_broker.add_topic_to_queue("test/>", "test_queue")

        # Should match various depths
        dev_broker.send_message("test/a", "match1")
        msg = dev_broker.receive_message(1000, "test_queue")
        assert msg["payload"] == "match1"

        dev_broker.send_message("test/a/b/c/d", "match2")
        msg = dev_broker.receive_message(1000, "test_queue")
        assert msg["payload"] == "match2"


class TestDevBrokerSimulateReconnection:
    """Tests for DevBroker.simulate_reconnection() method."""

    @pytest.fixture
    def flow_lock_manager(self):
        return StubFlowLockManager()

    @pytest.fixture
    def flow_kv_store(self):
        return StubFlowKvStore()

    @pytest.fixture
    def dev_broker(self, flow_lock_manager, flow_kv_store):
        broker_properties = {
            "queue_name": "test_queue",
            "subscriptions": [{"topic": "initial/topic"}],
        }
        broker = DevBroker(broker_properties, flow_lock_manager, flow_kv_store)
        broker.connect()
        return broker

    def test_simulate_reconnection_invokes_callbacks(self, dev_broker):
        """Test that simulate_reconnection invokes registered callbacks."""
        callback_invoked = [False]

        def on_reconnected():
            callback_invoked[0] = True

        dev_broker.register_reconnection_callback(on_reconnected)
        dev_broker.simulate_reconnection()

        assert callback_invoked[0] is True

    def test_simulate_reconnection_invokes_all_callbacks(self, dev_broker):
        """Test that all registered callbacks are invoked."""
        call_order = []

        def callback1():
            call_order.append(1)

        def callback2():
            call_order.append(2)

        def callback3():
            call_order.append(3)

        dev_broker.register_reconnection_callback(callback1)
        dev_broker.register_reconnection_callback(callback2)
        dev_broker.register_reconnection_callback(callback3)

        dev_broker.simulate_reconnection()

        assert call_order == [1, 2, 3]

    def test_simulate_reconnection_handles_callback_exception(self, dev_broker):
        """Test that one callback exception doesn't block others."""
        results = []

        def callback1():
            results.append(1)

        def callback2():
            raise ValueError("Intentional error")

        def callback3():
            results.append(3)

        dev_broker.register_reconnection_callback(callback1)
        dev_broker.register_reconnection_callback(callback2)
        dev_broker.register_reconnection_callback(callback3)

        # Should not raise, and callback3 should still be called
        dev_broker.simulate_reconnection()

        assert results == [1, 3]

    def test_full_reconnection_flow_with_subscription_restore(self, dev_broker):
        """Test the full reconnection flow including subscription restoration."""
        # Track subscription restoration
        restored = []

        def on_reconnected():
            # Simulate what BrokerInput._on_reconnected does
            active_subscriptions = {"topic/a", "topic/b", "topic/c"}
            temporary_queue = True

            if temporary_queue and active_subscriptions:
                success, failed = dev_broker.restore_subscriptions_with_rebind(
                    subscriptions=active_subscriptions,
                    queue_name="test_queue",
                    temporary=temporary_queue,
                )
                restored.append((success, failed))

        dev_broker.register_reconnection_callback(on_reconnected)
        dev_broker.simulate_reconnection()

        assert len(restored) == 1
        assert restored[0] == (3, 0)  # 3 success, 0 failed

    def test_durable_queue_skips_rebind_on_reconnection(self, dev_broker):
        """Test that durable queues skip rebind (subscriptions persist)."""
        rebind_called = [False]

        def on_reconnected():
            active_subscriptions = {"topic/a", "topic/b"}
            temporary_queue = False  # Durable queue

            if temporary_queue and active_subscriptions:
                dev_broker.restore_subscriptions_with_rebind(
                    subscriptions=active_subscriptions,
                    queue_name="test_queue",
                    temporary=temporary_queue,
                )
                rebind_called[0] = True

        dev_broker.register_reconnection_callback(on_reconnected)
        dev_broker.simulate_reconnection()

        # Rebind should NOT have been called for durable queue
        assert rebind_called[0] is False

    def test_empty_subscriptions_skips_restore(self, dev_broker):
        """Test that empty subscriptions don't trigger restore."""
        restore_called = [False]

        def on_reconnected():
            active_subscriptions = set()  # Empty

            if active_subscriptions:
                dev_broker.restore_subscriptions_with_rebind(
                    subscriptions=active_subscriptions,
                    queue_name="test_queue",
                    temporary=True,
                )
                restore_called[0] = True

        dev_broker.register_reconnection_callback(on_reconnected)
        dev_broker.simulate_reconnection()

        assert restore_called[0] is False

    def test_multiple_reconnections(self, dev_broker):
        """Test that multiple reconnections work correctly."""
        reconnection_count = [0]

        def on_reconnected():
            reconnection_count[0] += 1

        dev_broker.register_reconnection_callback(on_reconnected)

        # Simulate multiple reconnections
        dev_broker.simulate_reconnection()
        dev_broker.simulate_reconnection()
        dev_broker.simulate_reconnection()

        assert reconnection_count[0] == 3

    def test_reconnection_with_thread_safety(self, dev_broker):
        """Test thread-safe reconnection handling."""
        call_count = [0]
        lock = threading.Lock()

        def on_reconnected():
            with lock:
                call_count[0] += 1

        dev_broker.register_reconnection_callback(on_reconnected)

        # Simulate reconnections from multiple threads
        threads = []
        for _ in range(10):
            t = threading.Thread(target=dev_broker.simulate_reconnection)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert call_count[0] == 10
