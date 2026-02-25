"""Network-based DevBroker client that connects to a DevBrokerServer over TCP.

This client implements the Messaging interface, allowing it to be used as a
drop-in replacement for the in-process DevBroker when the broker runs on a
different host (e.g., when testing with Docker containers).

Supports automatic reconnection when the server restarts or the connection
drops. Dynamically-added subscriptions are tracked and re-established after
reconnect.
"""

import json
import logging
import os
import socket
import threading
import time
from enum import Enum
from typing import Any, Dict, List, Optional, Set

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
)
from ...common import Message_NACK_Outcome

log = logging.getLogger(__name__)

# Default timeout (seconds) for individual send/receive operations inside
# _send_command.  This prevents the command lock from being held indefinitely
# when the server stops responding.
_DEFAULT_CMD_TIMEOUT = 30


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

    Automatically reconnects when the connection drops (e.g., when the server
    restarts). Dynamically-added subscriptions are tracked and re-established
    after reconnect.

    Configuration via broker_properties:
        - dev_broker_host: Server hostname (default: "localhost")
        - dev_broker_port: Server port (default: 55555)
        - queue_name: Name of the queue to create/use
        - subscriptions: List of {"topic": "pattern"} dicts
    """

    def __init__(self, broker_properties: dict):
        super().__init__(broker_properties)
        self._host = broker_properties.get("dev_broker_host") or os.getenv("DEV_BROKER_HOST", "localhost")
        self._port = int(broker_properties.get("dev_broker_port") or os.getenv("DEV_BROKER_PORT", "55555"))
        self._socket: Optional[socket.socket] = None
        self._socket_file = None
        self._connected = False
        self._client_id = broker_properties.get(
            "client_name", f"network-client-{id(self)}"
        )
        self._lock = threading.Lock()
        self._reconnect_lock = threading.Lock()
        self.messaging_service = NetworkMessagingService()
        # For interface compatibility
        self.persistent_receiver = {}

        # Track dynamically added subscriptions for reconnect
        self._dynamic_subscriptions: Set[str] = set()

        # Shutdown event used to interrupt retry loops
        self._shutdown = threading.Event()

    def connect(self):
        """Connect to the remote dev broker server.

        Retries on connection refused errors (e.g. the server hasn't started
        yet).  The retry behaviour is controlled by broker_properties:
          - connect_retries: max attempts (default 0 = retry forever)
          - connect_retry_delay_ms: delay between attempts in ms (default 3000)
        """
        if self._connected:
            log.warning("NetworkDevBroker: Already connected")
            return

        max_retries = int(self.broker_properties.get("connect_retries", 0))
        retry_delay = int(self.broker_properties.get("connect_retry_delay_ms", 3000)) / 1000.0
        attempt = 0

        while not self._shutdown.is_set():
            attempt += 1
            try:
                log.info(
                    "NetworkDevBroker: Connecting to %s:%s (attempt %d)",
                    self._host, self._port, attempt,
                )
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._socket.settimeout(5)
                self._socket.connect((self._host, self._port))
                self._socket.settimeout(None)  # Back to blocking for normal I/O
                self._socket_file = self._socket.makefile("rb")

                # Send CONNECT command
                queue_name = self.broker_properties.get("queue_name", "")
                subscriptions_config = self.broker_properties.get("subscriptions") or []
                subscriptions = [s.get("topic", s) if isinstance(s, dict) else s for s in subscriptions_config]

                # Include dynamically added subscriptions
                all_subscriptions = list(subscriptions) + [
                    s for s in self._dynamic_subscriptions if s not in subscriptions
                ]

                connect_cmd = {
                    "cmd": CMD_CONNECT,
                    "client_id": self._client_id,
                    "queue_name": queue_name,
                    "subscriptions": all_subscriptions,
                }
                response = self._send_command(connect_cmd)

                if response.get("status") != STATUS_OK:
                    raise ConnectionError(
                        f"Connect failed: {response.get('error_message', 'Unknown error')}"
                    )

                self._connected = True
                log.info(
                    "NetworkDevBroker: Connected as %s with queue %s",
                    self._client_id, queue_name,
                )
                return

            except (ConnectionRefusedError, ConnectionResetError, OSError) as e:
                self._cleanup_socket()
                if max_retries > 0 and attempt > max_retries:
                    log.error("NetworkDevBroker: Connection failed after %d attempts: %s", attempt, e)
                    raise
                if max_retries > 0:
                    log.info(
                        "NetworkDevBroker: Connection refused, retrying in %.1fs (%d/%d)...",
                        retry_delay, attempt, max_retries,
                    )
                else:
                    log.info(
                        "NetworkDevBroker: Connection refused, retrying in %.1fs (attempt %d)...",
                        retry_delay, attempt,
                    )
                # Use Event.wait so shutdown can interrupt the sleep
                if self._shutdown.wait(retry_delay):
                    raise ConnectionError("NetworkDevBroker: Shutdown requested during connect retry") from e

            except Exception as e:
                log.error("NetworkDevBroker: Connection failed: %s", e)
                self._cleanup_socket()
                raise

        raise ConnectionError("NetworkDevBroker: Shutdown requested")

    def _reconnect(self) -> bool:
        """Attempt to reconnect after a connection drop.

        Returns True if reconnection succeeds, False otherwise.
        Thread-safe: only one reconnect attempt runs at a time.
        """
        if not self._reconnect_lock.acquire(blocking=False):
            return False

        try:
            log.warning("NetworkDevBroker: Connection lost, attempting to reconnect...")
            self._cleanup_socket()
            self._connected = False
            self.connect()
            log.info("NetworkDevBroker: Reconnected successfully")
            return True
        except Exception as e:
            log.error("NetworkDevBroker: Reconnect failed: %s", e)
            return False
        finally:
            self._reconnect_lock.release()

    def disconnect(self):
        """Disconnect from the remote dev broker."""
        self._shutdown.set()

        if not self._connected:
            return

        try:
            self._send_command({"cmd": CMD_DISCONNECT})
        except Exception as e:
            log.warning("NetworkDevBroker: Error during disconnect: %s", e)
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
            # Try to reconnect if we know we were previously connected
            if not self._reconnect():
                time.sleep(1)  # Back off before caller retries
                return None

        try:
            receive_cmd = {
                "cmd": CMD_RECEIVE,
                "timeout_ms": timeout_ms,
            }

            # Set socket timeout for the receive operation
            # Add buffer for network latency
            socket_timeout = (timeout_ms / 1000) + 5
            response = self._send_command(receive_cmd, timeout=socket_timeout)

            if response.get("status") == STATUS_TIMEOUT:
                return None

            if response.get("status") != STATUS_OK:
                log.error(
                    "NetworkDevBroker: Receive error: %s", response.get("error_message")
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
        except (BrokenPipeError, ConnectionError, ConnectionResetError, OSError) as e:
            log.warning("NetworkDevBroker: Connection error during receive: %s", e)
            self._connected = False
            self._reconnect()
            return None
        except Exception as e:
            log.error("NetworkDevBroker: Receive error: %s", e)
            self._connected = False
            return None

    def send_message(
        self,
        destination_name: str,
        payload: Any,
        user_properties: Dict = None,
        user_context: Dict = None,
    ):
        """Publish a message to a topic."""
        if not self._connected:
            if not self._reconnect():
                raise RuntimeError("NetworkDevBroker: Not connected and reconnect failed")

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

        last_error = None
        for attempt in range(2):
            try:
                response = self._send_command(publish_cmd)

                if response.get("status") != STATUS_OK:
                    log.error(
                        "NetworkDevBroker: Publish failed: %s", response.get("error_message")
                    )

                # Call callback if provided (same pattern as DevBroker)
                if user_context and "callback" in user_context:
                    user_context["callback"](user_context)
                return

            except (BrokenPipeError, ConnectionError, ConnectionResetError, OSError) as e:
                last_error = e
                log.warning("NetworkDevBroker: Connection error during publish: %s", e)
                self._connected = False
                if attempt == 0 and self._reconnect():
                    log.info("NetworkDevBroker: Retrying publish after reconnect")
                    continue
                break

        raise RuntimeError(
            f"NetworkDevBroker: Publish failed after reconnect: {last_error}"
        ) from last_error

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
        # Track the subscription for reconnect even if we fail to subscribe now
        self._dynamic_subscriptions.add(topic_str)

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
                log.info("NetworkDevBroker: Subscribed to %s", topic_str)
                return True
            else:
                log.error(
                    "NetworkDevBroker: Subscribe failed: %s", response.get("error_message")
                )
                return False

        except Exception as e:
            log.error("NetworkDevBroker: Subscribe error: %s", e)
            return False

    def remove_topic_from_queue(self, topic_str: str, queue_name: str) -> bool:
        """Remove a topic subscription from a specific queue."""
        self._dynamic_subscriptions.discard(topic_str)

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
                log.info("NetworkDevBroker: Unsubscribed from %s", topic_str)
                return True
            else:
                log.error(
                    "NetworkDevBroker: Unsubscribe failed: %s", response.get("error_message")
                )
                return False

        except Exception as e:
            log.error("NetworkDevBroker: Unsubscribe error: %s", e)
            return False

    def ack_message(self, message):
        """Acknowledge a message (no-op for dev broker)."""
        pass

    def nack_message(self, broker_message, outcome: Message_NACK_Outcome):
        """Negative acknowledge a message (no-op for dev broker)."""
        pass

    def _send_command(self, cmd: Dict[str, Any], timeout: float = None) -> Dict[str, Any]:
        """Send a command and receive the response.

        Args:
            cmd: The command dict to send.
            timeout: Socket timeout in seconds for this operation.
                     Defaults to _DEFAULT_CMD_TIMEOUT.
        """
        if timeout is None:
            timeout = _DEFAULT_CMD_TIMEOUT

        with self._lock:
            if not self._socket:
                raise RuntimeError("Socket not connected")

            # Always set a timeout so a hung server can't hold the lock forever
            self._socket.settimeout(timeout)
            try:
                # Send command
                data = (json.dumps(cmd) + "\n").encode("utf-8")
                self._socket.sendall(data)

                # Receive response
                response_line = self._socket_file.readline()
                if not response_line:
                    raise ConnectionError("Connection closed by server")

                return json.loads(response_line.decode("utf-8"))
            finally:
                # Reset to blocking for other operations
                if self._socket:
                    try:
                        self._socket.settimeout(None)
                    except Exception:
                        pass
