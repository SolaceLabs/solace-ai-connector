"""Tests for the base Messaging class and related functionality"""

import sys
import pytest
import queue
import threading
from unittest.mock import MagicMock, patch

sys.path.append("src")

from solace_ai_connector.common.messaging.messaging import Messaging
from solace_ai_connector.common.messaging.dev_broker_messaging import DevBroker, DevConnectionStatus
from solace_ai_connector.common.messaging.messaging_builder import MessagingServiceBuilder
from solace_ai_connector.common import Message_NACK_Outcome


class TestMessaging:
    """Tests for the base Messaging class"""

    def test_init(self):
        """Test that the Messaging class can be initialized"""
        broker_properties = {"test": "value"}
        messaging = Messaging(broker_properties)
        assert messaging.broker_properties == broker_properties

    def test_abstract_methods(self):
        """Test that the abstract methods raise NotImplementedError"""
        messaging = Messaging({})

        with pytest.raises(NotImplementedError):
            messaging.connect()

        with pytest.raises(NotImplementedError):
            messaging.disconnect()

        with pytest.raises(NotImplementedError):
            messaging.receive_message(1000, "queue_id")

        with pytest.raises(NotImplementedError):
            messaging.send_message("destination", "payload")


class TestDevBroker:
    """Tests for the DevBroker class"""

    @pytest.fixture
    def flow_lock_manager(self):
        """Create a mock flow lock manager"""
        lock_manager = MagicMock()
        lock_manager.get_lock.return_value = threading.RLock()
        return lock_manager

    @pytest.fixture
    def flow_kv_store(self):
        """Create a mock flow key-value store"""
        kv_store = MagicMock()
        kv_store.get.return_value = None
        return kv_store

    @pytest.fixture
    def dev_broker(self, flow_lock_manager, flow_kv_store):
        """Create a DevBroker instance"""
        broker_properties = {
            "broker_type": "dev_broker",
            "queue_name": "test_queue",
            "subscriptions": [{"topic": "test/topic"}],
        }
        return DevBroker(broker_properties, flow_lock_manager, flow_kv_store)

    def test_init(self, dev_broker, flow_lock_manager, flow_kv_store):
        """Test that the DevBroker class can be initialized"""
        assert dev_broker.broker_properties["broker_type"] == "dev_broker"
        assert dev_broker.flow_lock_manager == flow_lock_manager
        assert dev_broker.flow_kv_store == flow_kv_store
        assert not dev_broker.connected

        # Verify that the lock manager and kv store were used correctly
        flow_lock_manager.get_lock.assert_called_with("subscriptions")
        flow_kv_store.get.assert_any_call("dev_broker:subscriptions")
        flow_kv_store.get.assert_any_call("dev_broker:queues")

    def test_connect_disconnect(self, dev_broker):
        """Test connect and disconnect methods"""
        dev_broker.connect()
        assert dev_broker.connected
        assert dev_broker.get_connection_status() == DevConnectionStatus.CONNECTED

        dev_broker.disconnect()
        assert not dev_broker.connected
        assert dev_broker.get_connection_status() == DevConnectionStatus.DISCONNECTED

    def test_send_receive_message(self, dev_broker):
        """Test sending and receiving messages"""
        dev_broker.connect()

        # Send a message
        payload = {"test": "data"}
        user_properties = {"prop": "value"}
        dev_broker.send_message("test/topic", payload, user_properties)

        # Receive the message
        message = dev_broker.receive_message(1000, "test_queue")

        assert message is not None
        assert message["payload"] == payload
        assert message["topic"] == "test/topic"
        assert message["user_properties"] == user_properties

    def test_send_message_with_callback(self, dev_broker):
        """Test sending a message with a callback"""
        dev_broker.connect()

        # Create a callback
        callback_called = False

        def callback(context):
            nonlocal callback_called
            callback_called = True
            assert context["test"] == "context"

        # Send a message with the callback
        user_context = {"callback": callback, "test": "context"}
        dev_broker.send_message(
            "test/topic", {"test": "data"}, user_context=user_context
        )

        assert callback_called

    def test_topic_matching(self, dev_broker):
        """Test the topic matching functionality"""
        # Test exact match
        assert DevBroker._topic_matches("test/topic", "test/topic")

        # Test wildcard match
        assert DevBroker._topic_matches("test/[^/]+", "test/topic")

        # Test multi-level wildcard match
        assert DevBroker._topic_matches("test/.*", "test/topic/subtopic")

        # Test non-match
        assert not DevBroker._topic_matches("test/topic", "test/other")

    def test_subscription_to_regex(self):
        """Test the subscription to regex conversion"""
        assert DevBroker._subscription_to_regex("test/topic") == "test/topic"
        assert DevBroker._subscription_to_regex("test/*") == "test/[^/]+"
        assert DevBroker._subscription_to_regex("test/>") == "test/.*"

    def test_receive_timeout(self, dev_broker):
        """Test that receive_message times out correctly"""
        dev_broker.connect()

        # Try to receive a message with a short timeout
        message = dev_broker.receive_message(100, "test_queue")

        assert message is None

    def test_ack_nack_message(self, dev_broker):
        """Test ack and nack methods (which are no-ops in DevBroker)"""
        dev_broker.connect()

        # Send and receive a message
        dev_broker.send_message("test/topic", {"test": "data"})
        message = dev_broker.receive_message(1000, "test_queue")

        # These should not raise exceptions
        dev_broker.ack_message(message)
        dev_broker.nack_message(message, Message_NACK_Outcome.FAILED)


class TestMessagingServiceBuilder:
    """Tests for the MessagingServiceBuilder class"""

    @pytest.fixture
    def flow_lock_manager(self):
        """Create a mock flow lock manager"""
        return MagicMock()

    @pytest.fixture
    def flow_kv_store(self):
        """Create a mock flow key-value store"""
        return MagicMock()

    @pytest.fixture
    def stop_signal(self):
        """Create a mock stop signal"""
        return MagicMock()

    def test_build_dev_broker(self, flow_lock_manager, flow_kv_store, stop_signal):
        """Test building a DevBroker"""
        builder = MessagingServiceBuilder(
            flow_lock_manager, flow_kv_store, "test_broker", stop_signal
        )

        # Test with explicit dev_broker type
        broker = builder.from_properties({"broker_type": "dev_broker"}).build()
        assert isinstance(broker, DevBroker)

        # Test with dev_mode=True
        broker = builder.from_properties(
            {"broker_type": "solace", "dev_mode": True}
        ).build()
        assert isinstance(broker, DevBroker)

        # Test with dev_mode="true" string
        broker = builder.from_properties(
            {"broker_type": "solace", "dev_mode": "true"}
        ).build()
        assert isinstance(broker, DevBroker)

    @patch("solace_ai_connector.common.messaging.messaging_builder.SolaceMessaging")
    def test_build_solace_messaging(
        self, mock_solace, flow_lock_manager, flow_kv_store, stop_signal
    ):
        """Test building a SolaceMessaging instance"""
        builder = MessagingServiceBuilder(
            flow_lock_manager, flow_kv_store, "test_broker", stop_signal
        )

        # Test with explicit solace type
        broker_props = {"broker_type": "solace"}
        broker = builder.from_properties(broker_props).build()
        mock_solace.assert_called_with(broker_props, "test_broker", stop_signal)

        # Test with None type (defaults to solace)
        broker_props = {"broker_type": None}
        broker = builder.from_properties(broker_props).build()
        mock_solace.assert_called_with(broker_props, "test_broker", stop_signal)

    def test_build_unsupported_broker(
        self, flow_lock_manager, flow_kv_store, stop_signal
    ):
        """Test building with an unsupported broker type"""
        builder = MessagingServiceBuilder(
            flow_lock_manager, flow_kv_store, "test_broker", stop_signal
        )

        with pytest.raises(ValueError, match="Unsupported broker type"):
            builder.from_properties({"broker_type": "unsupported"}).build()
