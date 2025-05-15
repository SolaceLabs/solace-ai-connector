"""Input broker component for the Solace AI Event Connector"""

import time
from solace.messaging.utils.manageable import ApiMetrics, Metric as SolaceMetrics

from .broker_base import BrokerBase
from .broker_base import base_info
from ...common.utils import deep_merge
from ...common.log import log
from ...common.message import Message
from ...common.monitoring import Metrics
from ...common import Message_NACK_Outcome


info = deep_merge(
    base_info,
    {
        "class_name": "BrokerInput",
        "description": (
            "Connect to a messaging broker and receive messages from it. "
            "The component will output the payload, topic, and user properties of the message."
        ),
        "config_parameters": [
            {
                "name": "broker_queue_name",
                "required": False,
                "description": "Queue name for broker, if not provided it will use a temporary queue",
            },
            {
                "name": "temporary_queue",
                "required": False,
                "description": "Whether to create a temporary queue that will be deleted "
                "after disconnection, defaulted to True if broker_queue_name is not provided",
                "default": False,
            },
            {
                "name": "broker_subscriptions",
                "required": True,
                "description": "Subscriptions for broker",
            },
            {
                "name": "payload_encoding",
                "required": False,
                "description": "Encoding for the payload (utf-8, base64, gzip, none)",
                "default": "utf-8",
            },
            {
                "name": "payload_format",
                "required": False,
                "description": "Format for the payload (json, yaml, text)",
                "default": "json",
            },
        ],
        "output_schema": {
            "type": "object",
            "properties": {
                "payload": {
                    "type": "string",
                },
                "topic": {
                    "type": "string",
                },
                "user_properties": {
                    "type": "object",
                },
            },
            "required": ["payload", "topic", "user_properties"],
        },
    },
)

# We always need a timeout so that we can check if we should stop
DEFAULT_TIMEOUT_MS = 1000


class BrokerInput(BrokerBase):

    def __init__(self, module_info=None, **kwargs):
        module_info = module_info or info
        super().__init__(module_info, **kwargs)
        self.need_acknowledgement = True
        self.temporary_queue = self.get_config("temporary_queue", False)
        # If broker_queue_name is not provided, use temporary queue
        if not self.get_config("broker_queue_name"):
            self.temporary_queue = True
            self.broker_properties["temporary_queue"] = True
            # Generating a UUID for the queue name
            self.broker_properties["queue_name"] = self.generate_uuid()
        self.connect()

    def invoke(self, message, data):
        return {
            "payload": message.get_payload(),
            "topic": message.get_topic(),
            "user_properties": message.get_user_properties(),
        }

    def get_next_message(self, timeout_ms=None):
        try:

            if timeout_ms is None:
                timeout_ms = DEFAULT_TIMEOUT_MS
            broker_message = self.messaging_service.receive_message(
                timeout_ms, self.broker_properties["queue_name"]
            )
            if not broker_message:
                return None

            self.current_broker_message = broker_message

            # Create a message object
            msg = Message(
                payload=None,
                topic=None,
                user_properties=None,
            )
            payload = broker_message.get("payload")
            topic = broker_message.get("topic")
            user_properties = broker_message.get("user_properties", {})

            msg.payload = payload
            msg.topic = topic
            msg.user_properties = user_properties

            # add nack callback to the message
            callback = (
                self.get_negative_acknowledgement_callback()
            )  # pylint: disable=assignment-from-none
            if callback is not None:
                msg.add_negative_acknowledgements(callback)
            else:
                log.error("No callback for negative acknowledgement found. ")

            payload = self.decode_payload(payload)

            log.debug("Received message from broker.")

            # update the message with the decoded payload
            msg.payload = payload

            return msg
        except Exception as e:
            log.error("Error receiving message from broker")
            self.handle_negative_acknowledgements(msg, e)
            raise ValueError("Error receiving message from broker") from None

    def acknowledge_message(self, broker_message):
        self.messaging_service.ack_message(broker_message)

    def negative_acknowledge_message(
        self, broker_message, nack=Message_NACK_Outcome.REJECTED
    ):
        """
        Negative acknowledge a message
        Args:
            broker_message: The message to NACK
            nack: The type of NACK to send (FAILED or REJECTED)
        """
        if nack == Message_NACK_Outcome.FAILED:
            self.messaging_service.nack_message(
                broker_message, Message_NACK_Outcome.FAILED
            )
        else:
            self.messaging_service.nack_message(
                broker_message, Message_NACK_Outcome.REJECTED
            )

    def get_acknowledgement_callback(self):
        current_broker_message = self.current_broker_message
        return lambda: self.acknowledge_message(current_broker_message)

    def get_negative_acknowledgement_callback(self):
        """
        Get a callback function for negative acknowledgement
        """
        current_broker_message = self.current_broker_message

        def callback(nack):
            return self.negative_acknowledge_message(current_broker_message, nack)

        return callback

    def get_connection_status(self):
        return self.messaging_service.get_connection_status()

    def get_metrics(self):
        required_metrics = [
            Metrics.SOLCLIENT_STATS_RX_SETTLE_ACCEPTED,
            Metrics.SOLCLIENT_STATS_RX_SETTLE_FAILED,
            Metrics.SOLCLIENT_STATS_RX_SETTLE_REJECTED,
            Metrics.SOLCLIENT_STATS_TX_TOTAL_CONNECTION_ATTEMPTS,
        ]
        stats_dict = {}
        metrics: "ApiMetrics" = self.messaging_service.messaging_service.metrics()
        for metric_key in required_metrics:
            metric = SolaceMetrics(metric_key.value)
            stats_dict[metric_key] = {
                "value": metrics.get_value(SolaceMetrics(metric)),
                "timestamp": int(time.time()),
            }

        return stats_dict
