# solace-messaging.py - use solace-pubsubplus as a messaging service

import logging
import os
import certifi
import threading
import concurrent.futures
from enum import Enum

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
from ...common import Message_NACK_Outcome


class ConnectionStatus(Enum):
    RECONNECTING = 2
    CONNECTED = 1
    DISCONNECTED = 0


class ConnectionStrategy(Enum):
    FOREVER_RETRY = "forever_retry"
    PARAMETRIZED_RETRY = "parametrized_retry"


def change_connection_status(connection_properties: dict, status):
    with connection_properties["lock"]:
        connection_properties["status"] = status


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
            payload = payload.decode()

        # topic = message.get_destination_name()
        self.receiver.ack(message)


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

    def __init__(
        self,
        stop_signal,
        strategy,
        retry_count,
        retry_interval,
        connection_properties,
        error_prefix="",
    ):
        self.stop_signal = stop_signal
        self.error_prefix = error_prefix
        self.retry_count = retry_count
        self.retry_interval = retry_interval
        self.connection_properties = connection_properties

        try:
            self.strategy = ConnectionStrategy(strategy)
        except ValueError:
            log.error(
                f"{self.error_prefix} Invalid reconnection strategy: {strategy}. Using default strategy."
            )
            self.strategy = ConnectionStrategy.FOREVER_RETRY

    def on_reconnected(self, service_event: ServiceEvent):
        change_connection_status(self.connection_properties, ConnectionStatus.CONNECTED)
        log.info(f"{self.error_prefix} Successfully reconnected to broker.")

    def on_reconnecting(self, event: "ServiceEvent"):
        change_connection_status(
            self.connection_properties, ConnectionStatus.RECONNECTING
        )

        def log_reconnecting():

            while (
                not self.stop_signal.is_set()
                and self.connection_properties["status"]
                == ConnectionStatus.RECONNECTING
            ):
                # update retry count
                if self.strategy == ConnectionStrategy.PARAMETRIZED_RETRY:
                    if self.retry_count <= 0:
                        log.error(
                            f"{self.error_prefix} Reconnection attempts exhausted. Stopping..."
                        )
                        break
                    else:
                        self.retry_count -= 1

                log.info(
                    f"{self.error_prefix} Reconnecting to broker...",
                )
                self.stop_signal.wait(timeout=self.retry_interval / 1000)

        log_thread = threading.Thread(target=log_reconnecting, daemon=True)
        log_thread.start()

    def on_service_interrupted(self, event: "ServiceEvent"):
        change_connection_status(
            self.connection_properties, ConnectionStatus.DISCONNECTED
        )
        log.error(f"{self.error_prefix} Service interrupted")


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

    def __init__(self, broker_properties: dict, broker_name, stop_signal):
        super().__init__(broker_properties)
        self.persistent_receivers = []
        self.messaging_service = None
        self.service_handler = None
        self.publisher = None
        self.persistent_receiver: PersistentMessageReceiver = None
        self.stop_signal = stop_signal
        self.connection_properties = {
            "status": ConnectionStatus.DISCONNECTED,
            "lock": threading.Lock(),
        }

        self.error_prefix = f"broker[{broker_name}]:"
        # MessagingService.set_core_messaging_log_level(
        #     level="DEBUG", file="/home/efunnekotter/core.log"
        # )
        # set_python_solace_log_level("DEBUG")

    def __del__(self):
        change_connection_status(
            self.connection_properties, ConnectionStatus.DISCONNECTED
        )
        self.disconnect()

    def connect(self):
        try:
            # Build A messaging service with a reconnection strategy of 20 retries over
            # an interval of 3 seconds
            broker_props = {
                "solace.messaging.transport.host": self.broker_properties.get("host"),
                "solace.messaging.service.vpn-name": self.broker_properties.get(
                    "vpn_name"
                ),
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
                or os.path.dirname(certifi.where())
                or "/usr/share/ca-certificates/mozilla/",
            }

            try:
                if "reconnection_strategy" in self.broker_properties:
                    strategy = ConnectionStrategy(
                        self.broker_properties.get("reconnection_strategy")
                    )
                else:
                    log.info(
                        f"{self.error_prefix} reconnection_strategy not provided, using default value of forever_retry"
                    )
                    strategy = ConnectionStrategy.FOREVER_RETRY
            except ValueError:
                log.warning(
                    f"{self.error_prefix} Invalid reconnection strategy: {self.broker_properties.get('reconnection_strategy')}. Using default Forever Retry strategy."
                )
                strategy = ConnectionStrategy.FOREVER_RETRY

            retry_interval = 3000  # default
            retry_count = 20  # default
            if strategy == ConnectionStrategy.FOREVER_RETRY:
                retry_interval = self.broker_properties.get("retry_interval")
                if not retry_interval:
                    log.warning(
                        f"{self.error_prefix} retry_interval not provided, using default value of 3000 milliseconds"
                    )
                    retry_interval = 3000
                self.messaging_service = (
                    MessagingService.builder()
                    .from_properties(broker_props)
                    .with_reconnection_retry_strategy(
                        RetryStrategy.forever_retry(retry_interval)
                    )
                    .with_connection_retry_strategy(
                        RetryStrategy.forever_retry(retry_interval)
                    )
                    .build()
                )
            elif strategy == ConnectionStrategy.PARAMETRIZED_RETRY:
                retry_count = self.broker_properties.get("retry_count")
                retry_interval = self.broker_properties.get("retry_interval")
                if not retry_count:
                    log.warning(
                        f"{self.error_prefix} retry_count not provided, using default value of 20"
                    )
                    retry_count = 20
                if not retry_interval:
                    log.warning(
                        f"{self.error_prefix} retry_interval not provided, using default value of 3000"
                    )
                    retry_interval = 3000
                self.messaging_service = (
                    MessagingService.builder()
                    .from_properties(broker_props)
                    .with_reconnection_retry_strategy(
                        RetryStrategy.parametrized_retry(retry_count, retry_interval)
                    )
                    .with_connection_retry_strategy(
                        RetryStrategy.parametrized_retry(retry_count, retry_interval)
                    )
                    .build()
                )

            # Blocking connect thread
            result = self.messaging_service.connect_async()

            # log connection attempts
            # note: the connection/reconnection handler API does not log connection attempts
            self.stop_connection_log = threading.Event()

            def log_connecting():
                temp_retry_count = retry_count
                while not (
                    self.stop_signal.is_set()
                    or self.stop_connection_log.is_set()
                    or result.done()
                ):
                    # update retry count
                    if strategy == ConnectionStrategy.PARAMETRIZED_RETRY:
                        if temp_retry_count <= 0:
                            log.error(
                                f"{self.error_prefix} Connection attempts exhausted. Stopping..."
                            )
                            break
                        else:
                            temp_retry_count -= 1

                    log.info(f"{self.error_prefix} Connecting to broker...")
                    self.stop_signal.wait(timeout=retry_interval / 1000)

            log_thread = threading.Thread(target=log_connecting, daemon=True)
            log_thread.start()

            # wait for the connection to complete
            while not self.stop_signal.is_set():
                done, _ = concurrent.futures.wait([result], timeout=0.1)
                if done:
                    break

            # disconnect and raise an exception if the stop signal is set
            if self.stop_signal.is_set():
                log.error(f"{self.error_prefix} Stopping connection attempt")
                self.disconnect()
                raise KeyboardInterrupt("Stopping connection attempt") from None

            self.stop_connection_log.set()
            log.info(f"{self.error_prefix} Successfully connected to broker.")

            # change connection status to connected
            change_connection_status(
                self.connection_properties, ConnectionStatus.CONNECTED
            )

            # Event Handling for the messaging service
            self.service_handler = ServiceEventHandler(
                self.stop_signal,
                strategy,
                retry_count,
                retry_interval,
                self.connection_properties,
                self.error_prefix,
            )
            self.messaging_service.add_reconnection_listener(self.service_handler)
            self.messaging_service.add_reconnection_attempt_listener(
                self.service_handler
            )
            self.messaging_service.add_service_interruption_listener(
                self.service_handler
            )

            # Create a publisher
            self.publisher: PersistentMessagePublisher = (
                self.messaging_service.create_persistent_message_publisher_builder().build()
            )
            self.publisher.start()

            publish_receipt_listener = MessagePublishReceiptListenerImpl()
            self.publisher.set_message_publish_receipt_listener(
                publish_receipt_listener
            )

            if "queue_name" in self.broker_properties and self.broker_properties.get(
                "queue_name"
            ):
                self.bind_to_queue(
                    self.broker_properties.get("queue_name"),
                    self.broker_properties.get("subscriptions"),
                    self.broker_properties.get("temporary_queue"),
                    self.broker_properties.get("max_redelivery_count"),
                    self.broker_properties.get("create_queue_on_start"),
                )
        except KeyboardInterrupt:  # pylint: disable=broad-except
            raise KeyboardInterrupt from None
        except Exception as e:
            raise ValueError("Error in broker connection") from None

    def bind_to_queue(
        self,
        queue_name: str,
        subscriptions: list = None,
        temporary: bool = False,
        max_redelivery_count: int = None,
        create_queue_on_start: bool = True,
    ):
        if subscriptions is None:
            subscriptions = []

        if temporary:
            queue = Queue.non_durable_exclusive_queue(queue_name)
        else:
            queue = Queue.durable_exclusive_queue(queue_name)

        # Create a queue if create_queue_on_start is set to True
        if create_queue_on_start:
            missing_resources_creation_strategy = (
                MissingResourcesCreationStrategy.CREATE_ON_START
            )
        else:
            missing_resources_creation_strategy = (
                MissingResourcesCreationStrategy.DO_NOT_CREATE
            )

        try:
            # Build a receiver and bind it to the queue
            self.persistent_receiver: PersistentMessageReceiver = (
                self.messaging_service.create_persistent_message_receiver_builder()
                .with_missing_resources_creation_strategy(
                    missing_resources_creation_strategy
                )
                .with_required_message_outcome_support(
                    Message_NACK_Outcome.FAILED, Message_NACK_Outcome.REJECTED
                )
                .build(queue)
            )

            # set maximum redelivery count for the queue
            if max_redelivery_count != None:
                try:
                    end_point_props = {
                        "ENDPOINT_MAXMSG_REDELIVERY": str(max_redelivery_count),
                    }
                    self.persistent_receiver._end_point_props = {
                        **self.persistent_receiver._end_point_props,
                        **end_point_props,
                    }
                except Exception:
                    log.error(f"{self.error_prefix} Error setting max redelivery count")

            self.persistent_receiver.start()

            log.debug(
                f"{self.error_prefix} Persistent receiver started... Bound to Queue [%s] (Temporary: %s)",
                queue.get_name(),
                temporary,
            )

        # Handle API exception
        except PubSubPlusClientError:
            log.warning(
                f"{self.error_prefix} Error creating persistent receiver for queue [%s]",
                queue_name,
            )
            raise exception

        # Add to list of receivers
        self.persistent_receivers.append(self.persistent_receiver)

        # If subscriptions are provided, add them to the receiver
        if create_queue_on_start and subscriptions:
            for subscription in subscriptions:
                sub = TopicSubscription.of(subscription.get("topic"))
                self.persistent_receiver.add_subscription(sub)
                log.debug(f"{self.error_prefix} Subscribed to topic: %s", subscription)

        return self.persistent_receiver

    def disconnect(self):
        try:
            self.messaging_service.disconnect()
            change_connection_status(
                self.connection_properties, ConnectionStatus.DISCONNECTED
            )
        except Exception:  # pylint: disable=broad-except
            log.debug(f"{self.error_prefix} Error disconnecting")

    def get_connection_status(self):
        return self.connection_properties["status"]

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

    def receive_message(self, timeout_ms, queue_id):
        broker_message = self.persistent_receivers[0].receive_message(timeout_ms)
        if broker_message is None:
            return None

        # Convert Solace message to dictionary format
        return {
            "payload": broker_message.get_payload_as_string()
            or broker_message.get_payload_as_bytes(),
            "topic": broker_message.get_destination_name(),
            "user_properties": broker_message.get_properties(),
            "_original_message": broker_message,  # Keep original message for acknowledgement
        }

    def subscribe(
        self, subscription: str, persistent_receiver: PersistentMessageReceiver
    ):
        sub = TopicSubscription.of(subscription)
        persistent_receiver.add_subscription(sub)

    def ack_message(self, broker_message):
        if "_original_message" in broker_message:
            self.persistent_receiver.ack(broker_message["_original_message"])
        else:
            log.warning(
                f"{self.error_prefix} Cannot acknowledge message: original Solace message not found"
            )

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
        if "_original_message" in broker_message:
            self.persistent_receiver.settle(
                broker_message["_original_message"], outcome
            )
        else:
            log.warning(
                f"{self.error_prefix} Cannot drop message: original Solace message not found"
            )
