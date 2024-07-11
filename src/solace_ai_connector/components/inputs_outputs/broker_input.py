"""Input broker component for the Solace AI Event Connector"""

import base64
import gzip
import json
import yaml  # pylint: disable=import-error

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
            "required": True,
            "description": "Queue name for broker",
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

    def decode_payload(self, payload):
        encoding = self.get_config("payload_encoding")
        payload_format = self.get_config("payload_format")
        if encoding == "base64":
            payload = base64.b64decode(payload)
        elif encoding == "gzip":
            payload = gzip.decompress(payload)
        elif encoding == "utf-8" and (
            isinstance(payload, bytes) or isinstance(payload, bytearray)
        ):
            payload = payload.decode("utf-8")
        if payload_format == "json":
            payload = json.loads(payload)
        elif payload_format == "yaml":
            payload = yaml.safe_load(payload)
        return payload

    def acknowledge_message(self, broker_message):
        self.messaging_service.ack_message(broker_message)

    def get_acknowledgement_callback(self):
        current_broker_message = self.current_broker_message
        return lambda: self.acknowledge_message(current_broker_message)
