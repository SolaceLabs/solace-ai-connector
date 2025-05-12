"""Integration tests for the messaging module

Note: When testing with multiple DevBroker instances, it's important to use the same
flow_lock_manager and flow_kv_store for all instances to ensure they share the same
subscription and queue data. This is because the DevBroker uses these objects to store
its state, and different instances will not be able to communicate with each other
unless they share the same state.

The DevBroker uses a different wildcard syntax than Solace:
- '*' is a single-level wildcard (matches exactly one level)
- '>' is a multi-level wildcard (matches one or more levels)

For example:
- 'a/*/c' matches 'a/b/c' but not 'a/b/d' or 'a/b/c/d'
- 'a/b/>' matches 'a/b/c' and 'a/b/c/d' but not 'a/c/d'
"""

import sys
import pytest
import threading
import queue
from unittest.mock import MagicMock, patch

sys.path.append("src")

from solace_ai_connector.common.messaging.messaging_builder import MessagingServiceBuilder
from solace_ai_connector.common.messaging.dev_broker_messaging import DevBroker
from solace_ai_connector.common.message import Message
from solace_ai_connector.common import Message_NACK_Outcome


class TestMessagingIntegration:
    """Integration tests for the messaging module"""

    @pytest.fixture
    def flow_lock_manager(self):
        """Create a mock flow lock manager"""
        lock_manager = MagicMock()
        lock_manager.get_lock.return_value = threading.RLock()
        return lock_manager

    @pytest.fixture
    def flow_kv_store(self):
        """Create a mock flow key-value store that properly handles DevBroker state"""
        # Use a real dictionary to store the state
        store_dict = {}

        # Create a mock that uses the dictionary
        kv_store = MagicMock()
        kv_store.get.side_effect = lambda key: store_dict.get(key)
        kv_store.set.side_effect = lambda key, value: store_dict.update({key: value})

        return kv_store

    @pytest.fixture
    def stop_signal(self):
        """Create a stop signal for testing"""
        return threading.Event()

    def test_dev_broker_messaging_flow(
        self, flow_lock_manager, flow_kv_store, stop_signal
    ):
        """Test a complete messaging flow using DevBroker"""
        # Create a messaging service builder
        builder = MessagingServiceBuilder(
            flow_lock_manager, flow_kv_store, "test_broker", stop_signal
        )

        # Build a dev broker
        # Note: Using '>' instead of '#' for multi-level wildcard in DevBroker
        broker_properties = {
            "broker_type": "dev_broker",
            "queue_name": "test_queue",
            "subscriptions": [{"topic": "test/topic/>"}],
        }
        broker = builder.from_properties(broker_properties).build()

        # Connect to the broker
        broker.connect()

        try:
            # Create a message to send
            payload = {"test": "data", "nested": {"value": 123}}
            user_properties = {"prop1": "value1", "prop2": "value2"}

            # Send the message
            broker.send_message("test/topic/subtopic", payload, user_properties)

            # Receive the message
            received_message = broker.receive_message(1000, "test_queue")

            # Verify the message
            assert received_message is not None
            assert received_message["payload"] == payload
            assert received_message["topic"] == "test/topic/subtopic"
            assert received_message["user_properties"] == user_properties

            # Acknowledge the message
            broker.ack_message(received_message)
        finally:
            # Disconnect from the broker
            broker.disconnect()

    def test_multiple_subscribers(self, flow_lock_manager, flow_kv_store, stop_signal):
        """Test multiple subscribers receiving the same message"""
        # For this test, we need to use the same flow_kv_store and flow_lock_manager
        # for all brokers to ensure they share the same subscription and queue data

        # Create a messaging service builder
        builder = MessagingServiceBuilder(
            flow_lock_manager, flow_kv_store, "test_broker", stop_signal
        )

        # Build dev brokers for subscribers first
        subscriber1_properties = {
            "broker_type": "dev_broker",
            "queue_name": "subscriber1_queue",
            "subscriptions": [{"topic": "test/topic"}],
        }
        subscriber1 = builder.from_properties(subscriber1_properties).build()
        subscriber1.connect()

        subscriber2_properties = {
            "broker_type": "dev_broker",
            "queue_name": "subscriber2_queue",
            "subscriptions": [{"topic": "test/topic"}],
        }
        subscriber2 = builder.from_properties(subscriber2_properties).build()
        subscriber2.connect()

        # Build a dev broker for the publisher
        publisher_properties = {
            "broker_type": "dev_broker",
            "queue_name": "publisher_queue",
        }
        publisher = builder.from_properties(publisher_properties).build()
        publisher.connect()

        try:
            # Send a message
            payload = {"test": "multiple_subscribers"}
            publisher.send_message("test/topic", payload)

            # Receive the message from both subscribers
            message1 = subscriber1.receive_message(1000, "subscriber1_queue")
            message2 = subscriber2.receive_message(1000, "subscriber2_queue")

            # Verify both subscribers received the message
            assert message1 is not None
            assert message1["payload"] == payload
            assert message1["topic"] == "test/topic"

            assert message2 is not None
            assert message2["payload"] == payload
            assert message2["topic"] == "test/topic"
        finally:
            # Disconnect all brokers
            publisher.disconnect()
            subscriber1.disconnect()
            subscriber2.disconnect()

    def test_topic_wildcards(self, flow_lock_manager, flow_kv_store, stop_signal):
        """Test topic wildcards for message routing"""
        # Create a messaging service builder
        builder = MessagingServiceBuilder(
            flow_lock_manager, flow_kv_store, "test_broker", stop_signal
        )

        # Build a dev broker with wildcard subscriptions
        broker_properties = {
            "broker_type": "dev_broker",
            "queue_name": "test_queue",
            "subscriptions": [
                {"topic": "a/*/c"},  # Single-level wildcard
                {"topic": "x/y/>"},  # Multi-level wildcard
            ],
        }
        broker = builder.from_properties(broker_properties).build()
        broker.connect()

        # Send messages that should match the wildcards
        broker.send_message("a/b/c", {"match": "single_wildcard"})
        broker.send_message("x/y/z", {"match": "multi_level_wildcard_1"})
        broker.send_message("x/y/z/1/2", {"match": "multi_level_wildcard_2"})

        # Send a message that should not match any subscription
        broker.send_message("a/b/d", {"match": "no_match"})

        # Receive the messages that matched
        message1 = broker.receive_message(1000, "test_queue")
        message2 = broker.receive_message(1000, "test_queue")
        message3 = broker.receive_message(1000, "test_queue")

        # Try to receive another message (should be None as the non-matching message wasn't routed)
        message4 = broker.receive_message(100, "test_queue")

        # Verify the messages
        assert message1 is not None
        assert message2 is not None
        assert message3 is not None
        assert message4 is None

        # Verify the messages were received in the order they were sent
        assert message1["payload"] == {"match": "single_wildcard"}
        assert message2["payload"] == {"match": "multi_level_wildcard_1"}
        assert message3["payload"] == {"match": "multi_level_wildcard_2"}

        # Disconnect the broker
        broker.disconnect()

    def test_message_nack(self, flow_lock_manager, flow_kv_store, stop_signal):
        """Test negative acknowledgment of messages"""
        # Create a messaging service builder
        builder = MessagingServiceBuilder(
            flow_lock_manager, flow_kv_store, "test_broker", stop_signal
        )

        # Build a dev broker
        broker_properties = {
            "broker_type": "dev_broker",
            "queue_name": "test_queue",
            "subscriptions": [{"topic": "test/topic"}],
        }
        broker = builder.from_properties(broker_properties).build()
        broker.connect()

        # Send a message
        broker.send_message("test/topic", {"test": "nack"})

        # Receive the message
        message = broker.receive_message(1000, "test_queue")

        # Verify the message
        assert message is not None
        assert message["payload"] == {"test": "nack"}

        # Nack the message with FAILED outcome
        broker.nack_message(message, Message_NACK_Outcome.FAILED)

        # Disconnect the broker
        broker.disconnect()

    def test_message_with_callback(self, flow_lock_manager, flow_kv_store, stop_signal):
        """Test sending a message with a callback"""
        # Create a messaging service builder
        builder = MessagingServiceBuilder(
            flow_lock_manager, flow_kv_store, "test_broker", stop_signal
        )

        # Build a dev broker
        broker_properties = {
            "broker_type": "dev_broker",
            "queue_name": "test_queue",
            "subscriptions": [{"topic": "test/topic"}],
        }
        broker = builder.from_properties(broker_properties).build()
        broker.connect()

        # Create a callback
        callback_called = False
        callback_context = None

        def callback(context):
            nonlocal callback_called, callback_context
            callback_called = True
            callback_context = context

        # Send a message with the callback
        user_context = {"callback": callback, "test_id": 12345}
        broker.send_message(
            "test/topic", {"test": "callback"}, user_context=user_context
        )

        # Verify the callback was called
        assert callback_called
        assert callback_context["test_id"] == 12345

        # Disconnect the broker
        broker.disconnect()
