"""Network-based DevBroker client that connects to a DevBrokerServer over TCP.

This client implements the Messaging interface, allowing it to be used as a
drop-in replacement for the in-process DevBroker when the broker runs on a
different host (e.g., when testing with Docker containers).
"""

import json
import logging
import socket
import threading
from enum import Enum
from typing import Any, Dict, List, Optional

from .messaging import Messaging
from .dev_broker_protocol import (
    CMD_CONNECT,
    CMD_DISCONNECT,
    CMD_PUBLISH,
    CMD_RECEIVE,
    CMD_SUBSCRIBE,
    CMD_UNSUBSCRIBE,
    STATUS_OK,
    STATUS_TIMEOUT,
    BrokerMessage,
)
from ...common import Message_NACK_Outcome

log = logging.getLogger(__name__)


class NetworkConnectionStatus(Enum):
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"


class NetworkMetricValue:
    """Placeholder for metrics (not implemented for network broker)."""

    def get_value(self, metric_name):
        return 0


class NetworkMessagingService:
    """Placeholder for messaging service metrics."""

    def metrics(self):
        return NetworkMetricValue()


class NetworkDevBroker(Messaging):
    """
    Network-based dev broker client that implements the Messaging interface.

    Connects to a DevBrokerServer over TCP and translates Messaging interface
    calls to network protocol commands.

    Configuration via broker_properties:
        - dev_broker_host: Server hostname (default: "localhost")
        - dev_broker_port: Server port (default: 55555)
        - queue_name: Name of the queue to create/use
        - subscriptions: List of {"topic": "pattern"} dicts
    """

    def __init__(self, broker_properties: dict):
        super().__init__(broker_properties)
        self._host = broker_properties.get("dev_broker_host", "localhost")
        self._port = int(broker_properties.get("dev_broker_port", 55555))
        self._socket: Optional[socket.socket] = None
        self._socket_file = None
        self._connected = False
        self._client_id = broker_properties.get(
            "client_name", f"network-client-{id(self)}"
        )
        self._lock = threading.Lock()
        self.messaging_service = NetworkMessagingService()
        # For interface compatibility
        self.persistent_receiver = {}

    def connect(self):
        """Connect to the remote dev broker server."""
        if self._connected:
            log.warning("NetworkDevBroker: Already connected")
            return

        try:
            log.info(
                f"NetworkDevBroker: Connecting to {self._host}:{self._port}"
            )
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.connect((self._host, self._port))
            self._socket_file = self._socket.makefile("rb")

            # Send CONNECT command
            queue_name = self.broker_properties.get("queue_name", "")
            subscriptions_config = self.broker_properties.get("subscriptions") or []
            subscriptions = [s.get("topic", s) if isinstance(s, dict) else s for s in subscriptions_config]

            connect_cmd = {
                "cmd": CMD_CONNECT,
                "client_id": self._client_id,
                "queue_name": queue_name,
                "subscriptions": subscriptions,
            }
            response = self._send_command(connect_cmd)

            if response.get("status") != STATUS_OK:
                raise ConnectionError(
                    f"Connect failed: {response.get('error_message', 'Unknown error')}"
                )

            self._connected = True
            log.info(
                f"NetworkDevBroker: Connected as {self._client_id} with queue {queue_name}"
            )

        except Exception as e:
            log.error(f"NetworkDevBroker: Connection failed: {e}")
            self._cleanup_socket()
            raise

    def disconnect(self):
        """Disconnect from the remote dev broker."""
        if not self._connected:
            return

        try:
            self._send_command({"cmd": CMD_DISCONNECT})
        except Exception as e:
            log.warning(f"NetworkDevBroker: Error during disconnect: {e}")
        finally:
            self._cleanup_socket()
            self._connected = False
            log.info("NetworkDevBroker: Disconnected")

    def _cleanup_socket(self):
        """Clean up socket resources."""
        if self._socket_file:
            try:
                self._socket_file.close()
            except Exception:
                pass
            self._socket_file = None

        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None

    def get_connection_status(self):
        """Return the current connection status."""
        return (
            NetworkConnectionStatus.CONNECTED
            if self._connected
            else NetworkConnectionStatus.DISCONNECTED
        )

    def receive_message(self, timeout_ms: int, queue_name: str):
        """Receive the next message from the queue with timeout."""
        if not self._connected:
            raise RuntimeError("NetworkDevBroker: Not connected")

        try:
            receive_cmd = {
                "cmd": CMD_RECEIVE,
                "timeout_ms": timeout_ms,
            }

            # Set socket timeout for the receive operation
            # Add buffer for network latency
            socket_timeout = (timeout_ms / 1000) + 5
            self._socket.settimeout(socket_timeout)

            response = self._send_command(receive_cmd)

            if response.get("status") == STATUS_TIMEOUT:
                return None

            if response.get("status") != STATUS_OK:
                log.error(
                    f"NetworkDevBroker: Receive error: {response.get('error_message')}"
                )
                return None

            message_data = response.get("message")
            if not message_data:
                return None

            # Return in the format expected by SAC
            return {
                "payload": message_data.get("payload"),
                "topic": message_data.get("topic", ""),
                "user_properties": message_data.get("user_properties", {}),
                "_message_id": message_data.get("message_id"),
            }

        except socket.timeout:
            return None
        except Exception as e:
            log.error(f"NetworkDevBroker: Receive error: {e}")
            return None
        finally:
            # Reset socket timeout
            if self._socket:
                self._socket.settimeout(None)

    def send_message(
        self,
        destination_name: str,
        payload: Any,
        user_properties: Dict = None,
        user_context: Dict = None,
    ):
        """Publish a message to a topic."""
        if not self._connected:
            raise RuntimeError("NetworkDevBroker: Not connected")

        try:
            # BrokerOutput encodes payload to bytes; decode for JSON transport
            if isinstance(payload, (bytes, bytearray)):
                try:
                    payload = json.loads(payload)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    payload = payload.decode("utf-8", errors="replace")

            publish_cmd = {
                "cmd": CMD_PUBLISH,
                "topic": destination_name,
                "payload": payload,
                "user_properties": user_properties or {},
            }
            response = self._send_command(publish_cmd)

            if response.get("status") != STATUS_OK:
                log.error(
                    f"NetworkDevBroker: Publish failed: {response.get('error_message')}"
                )

            # Call callback if provided (same pattern as DevBroker)
            if user_context and "callback" in user_context:
                user_context["callback"](user_context)

        except Exception as e:
            log.error(f"NetworkDevBroker: Publish error: {e}")
            raise

    def subscribe(self, subscription: str, queue_name: str):
        """Subscribe to a topic pattern."""
        return self.add_topic_to_queue(subscription, queue_name)

    def add_topic_subscription(self, topic_str: str, persistent_receiver=None):
        """Add a topic subscription to the default queue."""
        queue_name = self.broker_properties.get("queue_name")
        if not queue_name:
            log.error("NetworkDevBroker: No default queue configured for subscription")
            return False
        return self.add_topic_to_queue(topic_str, queue_name)

    def remove_topic_subscription(self, topic_str: str, persistent_receiver=None):
        """Remove a topic subscription from the default queue."""
        queue_name = self.broker_properties.get("queue_name")
        if not queue_name:
            log.error("NetworkDevBroker: No default queue configured")
            return False
        return self.remove_topic_from_queue(topic_str, queue_name)

    def add_topic_to_queue(self, topic_str: str, queue_name: str) -> bool:
        """Add a topic subscription to a specific queue."""
        if not self._connected:
            log.error("NetworkDevBroker: Cannot subscribe - not connected")
            return False

        try:
            subscribe_cmd = {
                "cmd": CMD_SUBSCRIBE,
                "topic_pattern": topic_str,
            }
            response = self._send_command(subscribe_cmd)

            if response.get("status") == STATUS_OK:
                log.info(f"NetworkDevBroker: Subscribed to {topic_str}")
                return True
            else:
                log.error(
                    f"NetworkDevBroker: Subscribe failed: {response.get('error_message')}"
                )
                return False

        except Exception as e:
            log.error(f"NetworkDevBroker: Subscribe error: {e}")
            return False

    def remove_topic_from_queue(self, topic_str: str, queue_name: str) -> bool:
        """Remove a topic subscription from a specific queue."""
        if not self._connected:
            log.error("NetworkDevBroker: Cannot unsubscribe - not connected")
            return False

        try:
            unsubscribe_cmd = {
                "cmd": CMD_UNSUBSCRIBE,
                "topic_pattern": topic_str,
            }
            response = self._send_command(unsubscribe_cmd)

            if response.get("status") == STATUS_OK:
                log.info(f"NetworkDevBroker: Unsubscribed from {topic_str}")
                return True
            else:
                log.error(
                    f"NetworkDevBroker: Unsubscribe failed: {response.get('error_message')}"
                )
                return False

        except Exception as e:
            log.error(f"NetworkDevBroker: Unsubscribe error: {e}")
            return False

    def ack_message(self, message):
        """Acknowledge a message (no-op for dev broker)."""
        pass

    def nack_message(self, broker_message, outcome: Message_NACK_Outcome):
        """Negative acknowledge a message (no-op for dev broker)."""
        pass

    def _send_command(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        """Send a command and receive the response."""
        with self._lock:
            if not self._socket:
                raise RuntimeError("Socket not connected")

            # Send command
            data = (json.dumps(cmd) + "\n").encode("utf-8")
            self._socket.sendall(data)

            # Receive response
            response_line = self._socket_file.readline()
            if not response_line:
                raise ConnectionError("Connection closed by server")

            return json.loads(response_line.decode("utf-8"))
