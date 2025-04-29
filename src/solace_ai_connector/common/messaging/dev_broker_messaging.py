"""This is a simple broker for testing purposes. It allows sending and receiving 
messages to/from queues. It supports subscriptions based on topics."""

from typing import Dict, List, Any
import queue
import re
from copy import deepcopy
from enum import Enum

from .messaging import Messaging
from ...common import Message_NACK_Outcome


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

    def connect(self):
        self.connected = True
        queue_name = self.broker_properties.get("queue_name")
        subscriptions = self.broker_properties.get("subscriptions", [])
        if queue_name:
            self.queues[queue_name] = queue.Queue()
            for subscription in subscriptions:
                self.subscribe(subscription["topic"], queue_name)

    def disconnect(self):
        self.connected = False

    def get_connection_status(self):
        return (
            DevConnectionStatus.CONNECTED
            if self.connected
            else DevConnectionStatus.DISCONNECTED
        )

    def receive_message(self, timeout_ms, queue_name: str):
        if not self.connected:
            raise RuntimeError("DevBroker is not connected") from None

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
            raise RuntimeError("DevBroker is not connected") from None

        message = {
            "payload": payload,
            "topic": destination_name,
            "user_properties": user_properties or {},
        }

        matching_queue_names = self._get_matching_queue_names(destination_name)

        for queue_name in matching_queue_names:
            # Clone the message for each queue to ensure isolation
            self.queues[queue_name].put(deepcopy(message))

        if user_context and "callback" in user_context:
            user_context["callback"](user_context)

    def subscribe(self, subscription: str, queue_name: str):
        if not self.connected:
            raise RuntimeError("DevBroker is not connected") from None

        subscription = self._subscription_to_regex(subscription)

        with self.subscriptions_lock:
            if queue_name not in self.queues:
                self.queues[queue_name] = queue.Queue()
            if subscription not in self.subscriptions:
                self.subscriptions[subscription] = []
            self.subscriptions[subscription].append(queue_name)

    def ack_message(self, message):
        pass

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
