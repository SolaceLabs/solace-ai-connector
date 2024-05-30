"""Output broker component for sending messages from the Solace AI Event Connector to a broker"""

import base64
import gzip
import json
import yaml


from ...common.log import log
from .broker_base import (
    BrokerBase,
)
from ...common.message import Message

info = {
    "class_name": "BrokerOutput",
    "description": (
        "Connect to a messaging broker and send messages to it. "
        "Note that this component requires that the data is transformed into the input schema."
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
        {
            "name": "propagate_acknowledgements",
            "required": False,
            "description": "Propagate acknowledgements from the broker to the previous components",
            "default": True,
        },
        {
            "name": "copy_user_properties",
            "required": False,
            "description": "Copy user properties from the input message",
            "default": False,
        },
        {
            "name": "decrement_ttl",
            "required": False,
            "description": "If present, decrement the user_properties.ttl by 1",
        },
        {
            "name": "discard_on_ttl_expiration",
            "required": False,
            "description": "If present, discard the message when the user_properties.ttl is 0",
            "default": False,
        },
    ],
    "input_schema": {
        "type": "object",
        "properties": {
            "payload": {
                "type": "any",
                "description": "Payload of the message sent to the broker",
            },
            "topic": {"type": "string", "description": "Topic to send the message to"},
            "user_properties": {
                "type": "object",
                "description": "User properties to send with the message",
            },
        },
        "required": ["payload", "topic"],
    },
}


class BrokerOutput(BrokerBase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.needs_acknowledgement = False
        self.propagate_acknowledgements = self.get_config("propagate_acknowledgements")
        self.copy_user_properties = self.get_config("copy_user_properties")
        self.decrement_ttl = self.get_config("decrement_ttl")
        self.connect()

    def invoke(self, message, data):
        return data

    def encode_payload(self, payload):
        encoding = self.get_config("payload_encoding")
        payload_format = self.get_config("payload_format")
        if encoding == "utf-8":
            if payload_format == "json":
                return json.dumps(payload).encode("utf-8")
            elif payload_format == "yaml":
                return yaml.dump(payload).encode("utf-8")
            else:
                return str(payload).encode("utf-8")
        elif encoding == "base64":
            if payload_format == "json":
                return base64.b64encode(json.dumps(payload).encode("utf-8"))
            elif payload_format == "yaml":
                return base64.b64encode(yaml.dump(payload).encode("utf-8"))
            else:
                return base64.b64encode(str(payload).encode("utf-8"))
        elif encoding == "gzip":
            if payload_format == "json":
                return gzip.compress(json.dumps(payload).encode("utf-8"))
            elif payload_format == "yaml":
                return gzip.compress(yaml.dump(payload).encode("utf-8"))
            else:
                return gzip.compress(str(payload).encode("utf-8"))
        else:
            if payload_format == "json":
                return json.dumps(payload)
            elif payload_format == "yaml":
                return yaml.dump(payload)
            else:
                return str(payload)

    def send_message(self, message: Message):
        egress_data = message.get_data("previous")
        payload = self.encode_payload(egress_data.get("payload", ""))
        topic = egress_data.get("topic")
        user_properties = {}
        if self.copy_user_properties:
            user_properties = message.get_user_properties()

        if egress_data.get("user_properties"):
            # Merge user properties from the input message with the user properties from the config
            user_properties.update(egress_data.get("user_properties"))

        if self.decrement_ttl and user_properties.get("ttl"):
            user_properties["ttl"] = int(user_properties["ttl"]) - 1

        if (
            self.get_config("discard_on_ttl_expiration")
            and user_properties.get("ttl") <= 0
        ):
            log.info("Discarding message due to TTL expiration: %s", message)
            return

        log.debug(
            "Sending message to broker: topic=%s, user_properties=%s, payload=%s",
            topic,
            user_properties,
            payload,
        )
        user_context = None
        if self.propagate_acknowledgements:
            user_context = {
                "message": message,
                "callback": self.handle_message_ack_from_broker,
            }
        self.messaging_service.send_message(
            payload=payload,
            destination_name=topic,
            user_properties=user_properties,
            user_context=user_context,
        )

    def handle_message_ack_from_broker(self, context):
        message = context.get("message")
        if message:
            message.call_acknowledgements()
        else:
            log.error("No message found in context for acknowledgement")
