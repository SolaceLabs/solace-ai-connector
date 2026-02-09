"""Tests for reconnection and subscription restoration functionality.

Tests use real BrokerInput and DevBroker instances to exercise the
production reconnection code path end-to-end, with no mocking.
"""

import sys
import pytest
import threading

sys.path.append("src")

from solace_ai_connector.common.messaging.dev_broker_messaging import DevBroker
from solace_ai_connector.components.inputs_outputs.broker_input import BrokerInput


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


def _make_broker_input(
    subscriptions=None,
    queue_name=None,
    temporary_queue=None,
    flow_lock_manager=None,
    flow_kv_store=None,
):
    """Create a BrokerInput backed by a DevBroker for testing."""
    if subscriptions is None:
        subscriptions = [{"topic": "test/topic"}]
    if flow_lock_manager is None:
        flow_lock_manager = StubFlowLockManager()
    if flow_kv_store is None:
        flow_kv_store = StubFlowKvStore()

    component_config = {
        "broker_type": "dev_broker",
        "broker_subscriptions": subscriptions,
        "broker_url": "tcp://localhost:55555",
        "broker_username": "test",
        "broker_password": "test",
        "broker_vpn": "test",
    }
    if queue_name is not None:
        component_config["broker_queue_name"] = queue_name
    if temporary_queue is not None:
        component_config["temporary_queue"] = temporary_queue

    return BrokerInput(
        config={
            "component_name": "test_input",
            "component_config": component_config,
        },
        flow_lock_manager=flow_lock_manager,
        flow_kv_store=flow_kv_store,
        stop_signal=threading.Event(),
        flow_name="test_flow",
        instance_name="test",
        index=0,
        component_index=0,
    )


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
        """Test that restore_subscriptions returns success counts."""
        subscriptions = {"topic/a", "topic/b", "topic/c"}

        success, failed = dev_broker.restore_subscriptions(subscriptions)

        assert success == 3
        assert failed == 0

    def test_dev_broker_restore_subscriptions_with_empty_set(self, dev_broker):
        """Test restore with empty subscription set."""
        subscriptions = set()

        success, failed = dev_broker.restore_subscriptions(subscriptions)

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


class TestBrokerInputReconnection:
    """Integration tests for BrokerInput reconnection using real DevBroker.

    These tests exercise the production BrokerInput._on_reconnected code path
    by creating a real BrokerInput backed by DevBroker, then calling
    _on_reconnected() directly.
    """

    def test_reconnection_restores_subscriptions_for_temporary_queue(self):
        """Reconnection calls restore_subscriptions for temporary queues."""
        broker_input = _make_broker_input(
            subscriptions=[{"topic": "test/topic/a"}, {"topic": "test/topic/b"}],
            temporary_queue=True,
        )
        dev_broker = broker_input.messaging_service

        # Spy on restore_subscriptions to verify it's called
        restore_calls = []
        original_restore = dev_broker.restore_subscriptions

        def spy_restore(subscriptions, cancel_event=None):
            restore_calls.append(subscriptions)
            return original_restore(subscriptions, cancel_event=cancel_event)

        dev_broker.restore_subscriptions = spy_restore

        broker_input._on_reconnected()

        assert len(restore_calls) == 1
        assert restore_calls[0] == {"test/topic/a", "test/topic/b"}

    def test_reconnection_skips_restore_for_durable_queue(self):
        """Reconnection does NOT call restore_subscriptions for durable queues."""
        broker_input = _make_broker_input(
            subscriptions=[{"topic": "test/topic"}],
            queue_name="my_durable_queue",
            temporary_queue=False,
        )
        dev_broker = broker_input.messaging_service

        restore_called = [False]
        original_restore = dev_broker.restore_subscriptions

        def spy_restore(subscriptions, cancel_event=None):
            restore_called[0] = True
            return original_restore(subscriptions, cancel_event=cancel_event)

        dev_broker.restore_subscriptions = spy_restore

        broker_input._on_reconnected()

        assert restore_called[0] is False

    def test_dynamically_added_subscriptions_restored_on_reconnection(self):
        """Subscriptions added via add_subscription are included in reconnection restore."""
        broker_input = _make_broker_input(
            subscriptions=[{"topic": "initial/topic"}],
            temporary_queue=True,
        )
        dev_broker = broker_input.messaging_service

        # Dynamically add a subscription via BrokerInput
        broker_input.add_subscription("dynamic/topic")

        # Verify it's tracked
        assert "dynamic/topic" in broker_input.get_active_subscriptions()

        # Spy on restore to capture the subscription set
        restore_calls = []
        original_restore = dev_broker.restore_subscriptions

        def spy_restore(subscriptions, cancel_event=None):
            restore_calls.append(subscriptions)
            return original_restore(subscriptions, cancel_event=cancel_event)

        dev_broker.restore_subscriptions = spy_restore

        broker_input._on_reconnected()

        assert len(restore_calls) == 1
        assert "initial/topic" in restore_calls[0]
        assert "dynamic/topic" in restore_calls[0]

    def test_reconnection_with_no_subscriptions_is_noop(self):
        """Reconnection with empty subscription set does not call restore."""
        broker_input = _make_broker_input(
            subscriptions=[],
            temporary_queue=True,
        )
        dev_broker = broker_input.messaging_service

        restore_called = [False]
        original_restore = dev_broker.restore_subscriptions

        def spy_restore(subscriptions, cancel_event=None):
            restore_called[0] = True
            return original_restore(subscriptions, cancel_event=cancel_event)

        dev_broker.restore_subscriptions = spy_restore

        broker_input._on_reconnected()

        assert restore_called[0] is False

    def test_concurrent_subscription_modification_during_reconnection(self):
        """Adding/removing subscriptions from threads during reconnection doesn't crash."""
        broker_input = _make_broker_input(
            subscriptions=[{"topic": f"topic/{i}"} for i in range(5)],
            temporary_queue=True,
        )
        errors = []

        def add_subs():
            try:
                for i in range(10):
                    broker_input.add_subscription(f"new/topic/{i}")
            except Exception as e:
                errors.append(e)

        def remove_subs():
            try:
                for i in range(5):
                    broker_input.remove_subscription(f"topic/{i}")
            except Exception as e:
                errors.append(e)

        def reconnect():
            try:
                for _ in range(3):
                    broker_input._on_reconnected()
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=add_subs),
            threading.Thread(target=remove_subs),
            threading.Thread(target=reconnect),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_broker_input_registers_reconnection_handler(self):
        """BrokerInput automatically registers its reconnection handler with DevBroker."""
        broker_input = _make_broker_input(
            subscriptions=[{"topic": "test/topic"}],
        )
        dev_broker = broker_input.messaging_service

        # BrokerInput._register_reconnection_handler should have registered
        # _on_reconnected as a callback
        assert len(dev_broker._reconnection_callbacks) == 1
        assert dev_broker._reconnection_callbacks[0] == broker_input._on_reconnected

    def test_removed_subscription_not_restored_on_reconnection(self):
        """Subscriptions removed via remove_subscription are excluded from restore."""
        broker_input = _make_broker_input(
            subscriptions=[{"topic": "keep/this"}, {"topic": "remove/this"}],
            temporary_queue=True,
        )
        dev_broker = broker_input.messaging_service

        # Remove one subscription
        broker_input.remove_subscription("remove/this")

        # Spy on restore
        restore_calls = []
        original_restore = dev_broker.restore_subscriptions

        def spy_restore(subscriptions, cancel_event=None):
            restore_calls.append(subscriptions)
            return original_restore(subscriptions, cancel_event=cancel_event)

        dev_broker.restore_subscriptions = spy_restore

        broker_input._on_reconnected()

        assert len(restore_calls) == 1
        assert "keep/this" in restore_calls[0]
        assert "remove/this" not in restore_calls[0]
