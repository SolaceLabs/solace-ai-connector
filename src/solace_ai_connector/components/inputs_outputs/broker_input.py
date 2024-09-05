"""Input broker component for the Solace AI Event Connector"""

from ...common.log import log
from .broker_base import BrokerBase
from ...common.message import Message

info = {
    "class_name": "BrokerInput",
    "description": (
        "Connect to a messaging broker and receive messages from it. "
        "The component will output the payload, topic, and user properties of the message."
    ),
    "config_parameters": [
        {
            "name": "broker_type",
            "required": True,
            "description": "Type of broker (Solace, MQTT, etc.)",
        },
        {
            "name": "broker_url",
            "required": True,
            "description": "Broker URL (e.g. tcp://localhost:55555)",
        },
        {
            "name": "broker_username",
            "required": True,
            "description": "Client username for broker",
        },
        {
            "name": "broker_password",
            "required": True,
            "description": "Client password for broker",
        },
        {
            "name": "broker_vpn",
            "required": True,
            "description": "Client VPN for broker",
        },
        {
            "name": "broker_queue_name",
            "required": False,
            "description": "Queue name for broker, if not provided it will use a temporary queue",
        },
        {
            "name": "temporary_queue",
            "required": False,
            "description": "Whether to create a temporary queue that will be deleted after disconnection, defaulted to True if broker_queue_name is not provided",
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
}

# We always need a timeout so that we can check if we should stop
DEFAULT_TIMEOUT_MS = 1000


class BrokerInput(BrokerBase):
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
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
        if timeout_ms is None:
            timeout_ms = DEFAULT_TIMEOUT_MS
        broker_message = self.messaging_service.receive_message(timeout_ms)
        if not broker_message:
            return None
        self.current_broker_message = broker_message
        payload = broker_message.get_payload_as_string()
        topic = broker_message.get_destination_name()
        if payload is None:
            payload = broker_message.get_payload_as_bytes()
        payload = self.decode_payload(payload)
        user_properties = broker_message.get_properties()
        log.debug(
            "Received message from broker: topic=%s, user_properties=%s, payload length=%d",
            topic,
            user_properties,
            len(payload) if payload is not None else 0,
        )
        return Message(payload=payload, topic=topic, user_properties=user_properties)

    def acknowledge_message(self, broker_message):
        self.messaging_service.ack_message(broker_message)

    def get_acknowledgement_callback(self):
        current_broker_message = self.current_broker_message
        return lambda: self.acknowledge_message(current_broker_message)
