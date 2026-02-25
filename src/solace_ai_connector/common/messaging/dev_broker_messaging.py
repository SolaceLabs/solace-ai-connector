"""This is a simple broker for testing purposes. It allows sending and receiving
messages to/from queues. It supports subscriptions based on topics."""

import logging
import os
import threading
from typing import Dict, List, Any, Optional
import queue
import re
from copy import deepcopy
from enum import Enum

from .messaging import Messaging
from ...common import Message_NACK_Outcome

log = logging.getLogger(__name__)

class DevConnectionStatus(Enum):
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"


class DevMetricValue:

    def get_value(self, metric_name):
        # Return 0 for all metrics
        return 0


class DevMessagingService:

    def metrics(self):
        return DevMetricValue()


class DevBroker(Messaging):

    def __init__(self, broker_properties: dict, flow_lock_manager, flow_kv_store):
        super().__init__(broker_properties)
        self.flow_lock_manager = flow_lock_manager
        self.flow_kv_store = flow_kv_store
        self.connected = False
        self.messaging_service = DevMessagingService()
        self.subscriptions_lock = self.flow_lock_manager.get_lock("subscriptions")
        with self.subscriptions_lock:
            self.subscriptions = self.flow_kv_store.get("dev_broker:subscriptions")
            if self.subscriptions is None:
                self.subscriptions: Dict[str, List[str]] = {}
                self.flow_kv_store.set("dev_broker:subscriptions", self.subscriptions)
            self.queues = self.flow_kv_store.get("dev_broker:queues")
            if self.queues is None:
                self.queues: Dict[str, queue.Queue] = {}
                self.flow_kv_store.set("dev_broker:queues", self.queues)

        # Need this to be able to use the same interface as the other brokers
        self.persistent_receiver = {}
        self._reconnection_callbacks = []
        self._reconnection_lock = threading.Lock()

    def connect(self):
        self.connected = True
        queue_name = self.broker_properties.get("queue_name")
        subscriptions = self.broker_properties.get("subscriptions", [])
        if queue_name:
            self.queues[queue_name] = queue.Queue()
            for subscription in subscriptions:
                self.subscribe(subscription["topic"], queue_name)

        # Start network server if enabled (only once across all DevBroker instances)
        self._maybe_start_network_server()

    def disconnect(self):
        self.connected = False

    def get_connection_status(self):
        return (
            DevConnectionStatus.CONNECTED
            if self.connected
            else DevConnectionStatus.DISCONNECTED
        )

    def register_reconnection_callback(self, callback):
        """Register a callback to be invoked on reconnection."""
        with self._reconnection_lock:
            self._reconnection_callbacks.append(callback)

    def restore_subscriptions(self, subscriptions: set, cancel_event=None):
        """No-op for DevBroker - subscriptions persist in memory."""
        return (len(subscriptions), 0)

    def receive_message(self, timeout_ms, queue_name: str):
        if not self.connected:
            raise RuntimeError("DevBroker is not connected")

        try:
            return self.queues[queue_name].get(timeout=timeout_ms / 1000)
        except queue.Empty:
            return None

    def send_message(
        self,
        destination_name: str,
        payload: Any,
        user_properties: Dict = None,
        user_context: Dict = None,
    ):
        if not self.connected:
            raise RuntimeError("DevBroker is not connected")

        message = {
            "payload": payload,
            "topic": destination_name,
            "user_properties": user_properties or {},
        }

        matching_queue_names = self._get_matching_queue_names(destination_name)

        for queue_name in matching_queue_names:
            # Clone the message for each queue to ensure isolation
            self.queues[queue_name].put(deepcopy(message))

        # Forward to network clients if a network server is running.
        # Skip if the message originated from a network client (already routed
        # by DevBrokerServer._handle_publish to avoid duplicates).
        from_network = user_context and user_context.get("_from_network")
        if not from_network:
            network_route_fn = self.flow_kv_store.get("dev_broker:network_route_fn")
            if network_route_fn:
                network_route_fn(destination_name, payload, user_properties)

        if user_context and "callback" in user_context:
            user_context["callback"](user_context)

    def subscribe(self, subscription: str, queue_name: str):
        if not self.connected:
            raise RuntimeError("DevBroker is not connected")

        subscription = self._subscription_to_regex(subscription)

        with self.subscriptions_lock:
            if queue_name not in self.queues:
                self.queues[queue_name] = queue.Queue()
            if subscription not in self.subscriptions:
                self.subscriptions[subscription] = []
            self.subscriptions[subscription].append(queue_name)

    def ack_message(self, message):
        pass

    def add_topic_subscription(self, topic_str: str, persistent_receiver=None):
        """Adds a topic subscription to the default queue (matches SolaceMessaging interface)"""
        queue_name = self.broker_properties.get("queue_name")
        if not queue_name:
            log.error("DevBroker: No default queue configured for subscription")
            return False
        return self.add_topic_to_queue(topic_str, queue_name)

    def remove_topic_subscription(self, topic_str: str, persistent_receiver=None):
        """Removes a topic subscription from the default queue (matches SolaceMessaging interface)"""
        queue_name = self.broker_properties.get("queue_name")
        if not queue_name:
            log.error("DevBroker: No default queue configured for subscription")
            return False
        return self.remove_topic_from_queue(topic_str, queue_name)

    def add_topic_to_queue(self, topic_str: str, queue_name: str) -> bool:
        """Adds a topic subscription (regex pattern) to the specified queue's list of subscriptions."""
        if not self.connected:
            log.error("DevBroker: Cannot add topic to queue. Not connected.")
            return False

        regex_pattern = self._subscription_to_regex(topic_str)
        with self.subscriptions_lock:
            if queue_name not in self.queues:
                log.error(
                    f"DevBroker: Queue '{queue_name}' does not exist. Cannot add subscription '{topic_str}'."
                )
                return False

            if regex_pattern not in self.subscriptions:
                self.subscriptions[regex_pattern] = []

            if queue_name not in self.subscriptions[regex_pattern]:
                self.subscriptions[regex_pattern].append(queue_name)
                log.info(
                    f"DevBroker: Added subscription '{topic_str}' (regex: '{regex_pattern}') to queue '{queue_name}'."
                )
            else:
                log.debug(
                    f"DevBroker: Subscription '{topic_str}' already exists for queue '{queue_name}'."
                )
        return True

    def remove_topic_from_queue(self, topic_str: str, queue_name: str) -> bool:
        """Removes a topic subscription (regex pattern) from the specified queue's list of subscriptions."""
        if not self.connected:
            log.error("DevBroker: Cannot remove topic from queue. Not connected.")
            return False

        regex_pattern = self._subscription_to_regex(topic_str)
        with self.subscriptions_lock:
            if (
                regex_pattern in self.subscriptions
                and queue_name in self.subscriptions[regex_pattern]
            ):
                self.subscriptions[regex_pattern].remove(queue_name)
                if not self.subscriptions[regex_pattern]:  # If list becomes empty
                    del self.subscriptions[regex_pattern]
                log.info(
                    f"DevBroker: Removed subscription '{topic_str}' (regex: '{regex_pattern}') from queue '{queue_name}'."
                )
                return True
            else:
                log.warning(
                    f"DevBroker: Subscription '{topic_str}' not found for queue '{queue_name}'. Cannot remove."
                )
                return False

    def nack_message(self, broker_message, outcome: Message_NACK_Outcome):
        """
        This method handles the negative acknowledgment (nack) of a broker message.
        If the broker message contains an "_original_message" key, it settles the message
        with the given outcome using the persistent receiver. If the "_original_message"
        key is not found, it logs a warning indicating that the original Solace message
        could not be found and therefore cannot be dropped.

        Args:
            broker_message (dict): The broker message to be nacked.
            outcome (Message_NACK_Outcome): The outcome to be used for settling the message.
        """
        pass

    def _get_matching_queue_names(self, topic: str) -> List[str]:
        matching_queue_names = []
        with self.subscriptions_lock:
            for subscription, queue_names in self.subscriptions.items():
                if self._topic_matches(subscription, topic):
                    matching_queue_names.extend(queue_names)
            return list(set(matching_queue_names))  # Remove duplicates

    @staticmethod
    def _topic_matches(subscription: str, topic: str) -> bool:
        return re.match(f"^{subscription}$", topic) is not None

    @staticmethod
    def _subscription_to_regex(subscription: str) -> str:
        return subscription.replace("*", "[^/]+").replace(">", ".*")

    # --- Network Server Support ---

    def _maybe_start_network_server(self):
        """Start network server if enabled in config and not already running."""
        # Check if network server is enabled via config or environment
        network_enabled = self.broker_properties.get(
            "dev_broker_network_enabled",
            os.getenv("DEV_BROKER_NETWORK_ENABLED", "").lower() in ("true", "1", "yes"),
        )

        if not network_enabled:
            return

        # Use flow_kv_store to ensure only one server is started
        with self.subscriptions_lock:
            existing_server = self.flow_kv_store.get("dev_broker:network_server")
            if existing_server is not None:
                # Server already running, store reference for this instance
                self._network_server = existing_server
                log.debug(
                    "DevBroker: Network server already running on port %d",
                    existing_server.port,
                )
                return

            # Start the server
            port = self.broker_properties.get(
                "dev_broker_network_port",
                int(os.getenv("DEV_BROKER_PORT", "55555")),
            )

            from .dev_broker_server import start_server_in_thread

            try:
                self._network_server = start_server_in_thread(
                    host="0.0.0.0", port=port, local_broker=self
                )
            except RuntimeError:
                log.error(
                    "DevBroker: Failed to start network server on port %d", port
                )
                return

            # Store in flow_kv_store so other DevBroker instances don't start another
            self.flow_kv_store.set("dev_broker:network_server", self._network_server)

            # Store a synchronous callback that all DevBroker instances can use
            # to forward messages to network clients
            server = self._network_server

            def network_route_fn(topic, payload, user_properties):
                import asyncio as _asyncio

                try:
                    _asyncio.run_coroutine_threadsafe(
                        server._route_message_to_network(
                            topic, payload, user_properties
                        ),
                        server._loop,
                    )
                except Exception:
                    pass  # Server may be shutting down

            self.flow_kv_store.set("dev_broker:network_route_fn", network_route_fn)

            log.info(
                "DevBroker: Network server started on port %d (enabled via config)",
                self._network_server.port,
            )

    def start_server(
        self,
        host: str = "0.0.0.0",
        port: Optional[int] = None,
    ) -> int:
        """
        Start a network server to allow remote clients to connect.

        This enables Docker containers or other remote processes to communicate
        with this DevBroker instance over TCP.

        Args:
            host: Host to bind to (default: all interfaces)
            port: Port to listen on. If None, uses DEV_BROKER_PORT env var
                  or defaults to 55555. Use 0 for auto-assign.

        Returns:
            The actual port the server is listening on.
        """
        if port is None:
            port = int(os.getenv("DEV_BROKER_PORT", "55555"))

        from .dev_broker_server import start_server_in_thread

        self._network_server = start_server_in_thread(
            host=host, port=port, local_broker=self
        )
        log.info(f"DevBroker: Network server started on port {self._network_server.port}")
        return self._network_server.port

    def stop_server(self):
        """Stop the network server if running."""
        if hasattr(self, "_network_server") and self._network_server:
            import asyncio

            if self._network_server._loop and self._network_server._loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self._network_server.stop(), self._network_server._loop
                )
            self._network_server = None
            log.info("DevBroker: Network server stopped")
