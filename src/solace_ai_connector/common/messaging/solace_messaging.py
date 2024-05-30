# solace-messaging.py - use solace-pubsubplus as a messaging service

import logging
import os

from solace.messaging.messaging_service import (
    MessagingService,
    ReconnectionListener,
    ReconnectionAttemptListener,
    ServiceInterruptionListener,
    ServiceEvent,
)
from solace.messaging.resources.queue import Queue
from solace.messaging.config.retry_strategy import RetryStrategy
from solace.messaging.receiver.persistent_message_receiver import (
    PersistentMessageReceiver,
)
from solace.messaging.publisher.persistent_message_publisher import (
    PersistentMessagePublisher,
    MessagePublishReceiptListener,
    PublishReceipt,
)
from solace.messaging.receiver.message_receiver import MessageHandler, InboundMessage
from solace.messaging.errors.pubsubplus_client_error import PubSubPlusClientError
from solace.messaging.config.missing_resources_creation_configuration import (
    MissingResourcesCreationStrategy,
)
from solace.messaging.resources.topic_subscription import TopicSubscription
from solace.messaging.resources.topic import Topic
from solace import SOLACE_LOGGING_CONFIG

from .messaging import Messaging
from ..log import log


class MessageHandlerImpl(MessageHandler):
    def __init__(self, persistent_receiver: PersistentMessageReceiver):
        self.receiver: PersistentMessageReceiver = persistent_receiver
        self.persistent_receiver: PersistentMessageReceiver = None

    def on_message(self, message: InboundMessage):
        # Check if the payload is a String or Byte, decode if its the later
        payload = (
            message.get_payload_as_string()
            if message.get_payload_as_string() is not None
            else message.get_payload_as_bytes()
        )
        if isinstance(payload, bytearray):
            print(f"Received a message of type: {type(payload)}. Decoding to string")
            payload = payload.decode()

        topic = message.get_destination_name()
        print("\n" + f"Received message on: {topic}")
        print("\n" + f"Message payload: {payload} \n")
        self.receiver.ack(message)
        # print("\n" + f"Message dump: {message} \n")


class MessagePublishReceiptListenerImpl(MessagePublishReceiptListener):
    def __init__(self, callback=None):
        self.callback = callback

    def on_publish_receipt(self, publish_receipt: PublishReceipt):
        if publish_receipt.user_context:
            callback = publish_receipt.user_context.get("callback")
            callback(publish_receipt.user_context)


# Inner classes for error handling
class ServiceEventHandler(
    ReconnectionListener, ReconnectionAttemptListener, ServiceInterruptionListener
):
    def on_reconnected(self, service_event: ServiceEvent):
        print("\non_reconnected")
        print(f"Error cause: {service_event.get_cause()}")
        print(f"Message: {service_event.get_message()}")

    def on_reconnecting(self, event: "ServiceEvent"):
        print("\non_reconnecting")
        print(f"Error cause: {event.get_cause()}")
        print(f"Message: {event.get_message()}")

    def on_service_interrupted(self, event: "ServiceEvent"):
        print("\non_service_interrupted")
        print(f"Error cause: {event.get_cause()}")
        print(f"Message: {event.get_message()}")


def set_python_solace_log_level(level: str):
    # get solace loggers
    loggers = SOLACE_LOGGING_CONFIG["loggers"]
    # update log level
    for logr in loggers:
        loggers.get(logr)["level"] = level
    # set logger config change
    logging.config.dictConfig(SOLACE_LOGGING_CONFIG)


# Create SolaceMessaging class inheriting from Messaging
class SolaceMessaging(Messaging):
    def __init__(self, broker_properties: dict):
        super().__init__(broker_properties)
        self.persistent_receivers = []
        self.messaging_service = None
        self.service_handler = None
        self.publisher = None
        self.persistent_receiver: PersistentMessageReceiver = None
        # MessagingService.set_core_messaging_log_level(
        #     level="DEBUG", file="/home/efunnekotter/core.log"
        # )
        # set_python_solace_log_level("DEBUG")

    def __del__(self):
        print("DESTRUCTOR: SolaceMessaging")
        self.disconnect()

    def connect(self):
        # Build A messaging service with a reconnection strategy of 20 retries over
        # an interval of 3 seconds
        broker_props = {
            "solace.messaging.transport.host": self.broker_properties.get("host"),
            "solace.messaging.service.vpn-name": self.broker_properties.get("vpn_name"),
            "solace.messaging.authentication.scheme.basic.username": self.broker_properties.get(
                "username"
            ),
            "solace.messaging.authentication.scheme.basic.password": self.broker_properties.get(
                "password"
            ),
            "solace.messaging.tls.trust-store-path": self.broker_properties.get(
                "trust_store_path"
            )
            or os.environ.get("TRUST_STORE")
            or "/usr/share/ca-certificates/mozilla/",
        }
        # print (f"Broker Properties: {self.broker_properties}")
        self.messaging_service = (
            MessagingService.builder()
            .from_properties(broker_props)
            .with_reconnection_retry_strategy(
                RetryStrategy.parametrized_retry(20, 3000)
            )
            .build()
        )

        # Blocking connect thread
        self.messaging_service.connect()

        # Event Handling for the messaging service
        self.service_handler = ServiceEventHandler()
        self.messaging_service.add_reconnection_listener(self.service_handler)
        self.messaging_service.add_reconnection_attempt_listener(self.service_handler)
        self.messaging_service.add_service_interruption_listener(self.service_handler)

        # Create a publisher
        self.publisher: PersistentMessagePublisher = (
            self.messaging_service.create_persistent_message_publisher_builder().build()
        )
        self.publisher.start()

        publish_receipt_listener = MessagePublishReceiptListenerImpl()
        self.publisher.set_message_publish_receipt_listener(publish_receipt_listener)

        if "queue_name" in self.broker_properties and self.broker_properties.get(
            "queue_name"
        ):
            self.bind_to_queue(
                self.broker_properties.get("queue_name"),
                self.broker_properties.get("subscriptions"),
            )

    def bind_to_queue(self, queue_name: str, subscriptions: list = None):
        if subscriptions is None:
            subscriptions = []

        durable_exclusive_queue = Queue.durable_exclusive_queue(queue_name)

        try:
            # Build a receiver and bind it to the durable exclusive queue
            self.persistent_receiver: PersistentMessageReceiver = (
                self.messaging_service.create_persistent_message_receiver_builder()
                .with_missing_resources_creation_strategy(
                    MissingResourcesCreationStrategy.CREATE_ON_START
                )
                .build(durable_exclusive_queue)
            )
            self.persistent_receiver.start()

            # Callback for received messages
            # self.persistent_receiver.receive_async(MessageHandlerImpl(persistent_receiver))
            log.debug(
                "Persistent receiver started... Bound to Queue [%s]",
                durable_exclusive_queue.get_name(),
            )

        # Handle API exception
        except PubSubPlusClientError as exception:
            print(f"\nMake sure queue {queue_name} exists on broker!", exception)

        # Add to list of receivers
        self.persistent_receivers.append(self.persistent_receiver)

        # If subscriptions are provided, add them to the receiver
        if subscriptions:
            for subscription in subscriptions:
                sub = TopicSubscription.of(subscription.get("topic"))
                self.persistent_receiver.add_subscription(sub)
                print(f"Subscribed to topic: {subscription}")

        return self.persistent_receiver

    def disconnect(self):
        try:
            self.messaging_service.disconnect()
        except Exception as exception:  # pylint: disable=broad-except
            print(f"Error disconnecting: {exception}")

    def is_connected(self):
        return self.messaging_service.is_connected()

    def send_message(
        self,
        destination_name: str,
        payload: str,
        user_properties: dict = None,
        user_context=None,
    ):
        # Create a topic destination
        destination = Topic.of(destination_name)

        # Encode the message if it is a string
        if isinstance(payload, str):
            payload = bytearray(payload.encode("utf-8"))

        # Convert to bytearray if bytes
        elif isinstance(payload, bytes):
            payload = bytearray(payload)

        # Publish the message
        self.publisher.publish(
            message=payload,
            destination=destination,
            additional_message_properties=user_properties,
            user_context=user_context,
        )

    def receive_message(self, timeout_ms):
        return self.persistent_receivers[0].receive_message(timeout_ms)

    def subscribe(
        self, subscription: str, persistent_receiver: PersistentMessageReceiver
    ):
        sub = TopicSubscription.of(subscription)
        persistent_receiver.add_subscription(sub)

    def ack_message(self, broker_message):
        self.persistent_receiver.ack(broker_message)
