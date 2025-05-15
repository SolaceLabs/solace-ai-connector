"""Tests for the SolaceMessaging class"""

import sys
import pytest
from unittest.mock import MagicMock, patch, call
import threading
import concurrent.futures

sys.path.append("src")

from solace_ai_connector.common.messaging.solace_messaging import (
    SolaceMessaging,
    ConnectionStatus,
    ConnectionStrategy,
    ServiceEventHandler,
    change_connection_status,
)
from solace_ai_connector.common import Message_NACK_Outcome


class TestSolaceMessaging:
    """Tests for the SolaceMessaging class"""

    @pytest.fixture
    def broker_properties(self):
        """Create broker properties for testing"""
        return {
            "broker_type": "solace",
            "host": "tcp://localhost:55555",
            "vpn_name": "test_vpn",
            "username": "test_user",
            "password": "test_pass",
            "queue_name": "test_queue",
            "subscriptions": [{"topic": "test/topic"}],
        }

    @pytest.fixture
    def stop_signal(self):
        """Create a stop signal for testing"""
        return threading.Event()

    @pytest.fixture
    def solace_messaging(self, broker_properties, stop_signal):
        """Create a SolaceMessaging instance with mocked dependencies"""
        with patch(
            "solace_ai_connector.common.messaging.solace_messaging.MessagingService"
        ):
            return SolaceMessaging(broker_properties, "test_broker", stop_signal)

    @patch("solace_ai_connector.common.messaging.solace_messaging.MessagingService")
    def test_disconnect(self, mock_messaging_service, solace_messaging):
        """Test disconnect method"""
        solace_messaging.messaging_service = mock_messaging_service
        solace_messaging.disconnect()

        mock_messaging_service.disconnect.assert_called_once()
        assert (
            solace_messaging.connection_properties["status"]
            == ConnectionStatus.DISCONNECTED
        )

    @patch("solace_ai_connector.common.messaging.solace_messaging.MessagingService")
    @patch("solace_ai_connector.common.messaging.solace_messaging.Topic")
    def test_send_message(self, mock_topic, mock_messaging_service, solace_messaging):
        """Test send_message method"""
        # Set up mocks
        mock_publisher = MagicMock()
        solace_messaging.publisher = mock_publisher
        mock_topic.of.return_value = "topic_destination"

        # Test with string payload
        solace_messaging.send_message(
            "test/topic", "test_payload", {"prop": "value"}, {"context": "data"}
        )
        mock_topic.of.assert_called_with("test/topic")
        mock_publisher.publish.assert_called_with(
            message=bytearray(b"test_payload"),
            destination="topic_destination",
            additional_message_properties={"prop": "value"},
            user_context={"context": "data"},
        )

        # Test with bytes payload
        solace_messaging.send_message("test/topic", b"test_bytes", {"prop": "value"})
        mock_publisher.publish.assert_called_with(
            message=bytearray(b"test_bytes"),
            destination="topic_destination",
            additional_message_properties={"prop": "value"},
            user_context=None,
        )

    def test_receive_message(self, solace_messaging):
        """Test receive_message method"""
        # Set up mock receiver
        mock_receiver = MagicMock()
        mock_message = MagicMock()
        mock_message.get_payload_as_string.return_value = "test_payload"
        mock_message.get_destination_name.return_value = "test/topic"
        mock_message.get_properties.return_value = {"prop": "value"}
        mock_receiver.receive_message.return_value = mock_message
        solace_messaging.persistent_receivers = [mock_receiver]

        # Test receive_message
        message = solace_messaging.receive_message(1000, "test_queue")

        mock_receiver.receive_message.assert_called_with(1000)
        assert message["payload"] == "test_payload"
        assert message["topic"] == "test/topic"
        assert message["user_properties"] == {"prop": "value"}
        assert message["_original_message"] == mock_message

    def test_receive_message_none(self, solace_messaging):
        """Test receive_message when no message is available"""
        # Set up mock receiver
        mock_receiver = MagicMock()
        mock_receiver.receive_message.return_value = None
        solace_messaging.persistent_receivers = [mock_receiver]

        # Test receive_message
        message = solace_messaging.receive_message(1000, "test_queue")

        mock_receiver.receive_message.assert_called_with(1000)
        assert message is None

    def test_ack_message(self, solace_messaging):
        """Test ack_message method"""
        # Set up mock receiver
        mock_receiver = MagicMock()
        solace_messaging.persistent_receiver = mock_receiver

        # Test with original message
        original_message = MagicMock()
        broker_message = {"_original_message": original_message}
        solace_messaging.ack_message(broker_message)

        mock_receiver.ack.assert_called_with(original_message)

        # Test without original message
        with patch(
            "solace_ai_connector.common.messaging.solace_messaging.log"
        ) as mock_log:
            solace_messaging.ack_message({})
            mock_log.warning.assert_called_once()

    def test_nack_message(self, solace_messaging):
        """Test nack_message method"""
        # Set up mock receiver
        mock_receiver = MagicMock()
        solace_messaging.persistent_receiver = mock_receiver

        # Test with original message
        original_message = MagicMock()
        broker_message = {"_original_message": original_message}
        solace_messaging.nack_message(broker_message, Message_NACK_Outcome.FAILED)

        mock_receiver.settle.assert_called_with(
            original_message, Message_NACK_Outcome.FAILED
        )

        # Test without original message
        with patch(
            "solace_ai_connector.common.messaging.solace_messaging.log"
        ) as mock_log:
            solace_messaging.nack_message({}, Message_NACK_Outcome.REJECTED)
            mock_log.warning.assert_called_once()


class TestServiceEventHandler:
    """Tests for the ServiceEventHandler class"""

    @pytest.fixture
    def stop_signal(self):
        """Create a stop signal for testing"""
        return threading.Event()

    @pytest.fixture
    def connection_properties(self):
        """Create connection properties for testing"""
        return {"status": ConnectionStatus.DISCONNECTED, "lock": threading.Lock()}

    @pytest.fixture
    def service_event_handler(self, stop_signal, connection_properties):
        """Create a ServiceEventHandler instance"""
        return ServiceEventHandler(
            stop_signal,
            "forever_retry",
            20,
            3000,
            connection_properties,
            "test_prefix:",
        )

    def test_init_invalid_strategy(self, stop_signal, connection_properties):
        """Test initialization with invalid strategy"""
        with patch(
            "solace_ai_connector.common.messaging.solace_messaging.log"
        ) as mock_log:
            handler = ServiceEventHandler(
                stop_signal,
                "invalid_strategy",
                20,
                3000,
                connection_properties,
                "test_prefix:",
            )
            assert handler.strategy == ConnectionStrategy.FOREVER_RETRY
            mock_log.error.assert_called_once()

    def test_on_reconnected(self, service_event_handler, connection_properties):
        """Test on_reconnected method"""
        mock_event = MagicMock()
        service_event_handler.on_reconnected(mock_event)
        assert connection_properties["status"] == ConnectionStatus.CONNECTED

    def test_on_reconnecting(self, service_event_handler, connection_properties):
        """Test on_reconnecting method"""
        mock_event = MagicMock()

        # Mock the threading.Thread to avoid starting a real thread
        with patch("threading.Thread") as mock_thread:
            service_event_handler.on_reconnecting(mock_event)
            assert connection_properties["status"] == ConnectionStatus.RECONNECTING
            mock_thread.assert_called_once()

    def test_on_service_interrupted(self, service_event_handler, connection_properties):
        """Test on_service_interrupted method"""
        mock_event = MagicMock()

        with patch(
            "solace_ai_connector.common.messaging.solace_messaging.log"
        ) as mock_log:
            service_event_handler.on_service_interrupted(mock_event)
            assert connection_properties["status"] == ConnectionStatus.DISCONNECTED
            mock_log.error.assert_called_once()


def test_change_connection_status():
    """Test the change_connection_status function"""
    connection_properties = {
        "status": ConnectionStatus.DISCONNECTED,
        "lock": threading.Lock(),
    }
    change_connection_status(connection_properties, ConnectionStatus.CONNECTED)
    assert connection_properties["status"] == ConnectionStatus.CONNECTED
