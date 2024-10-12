"""This component sends messages to a websocket connection."""

import json
from ...common.log import log
from ...common.utils import encode_payload
from ..component_base import ComponentBase

info = {
    "class_name": "WebsocketOutput",
    "description": "Send messages to a websocket connection.",
    "config_parameters": [
        {
            "name": "payload_encoding",
            "required": False,
            "description": "Encoding for the payload (utf-8, base64, gzip, none)",
            "default": "none",
        },
        {
            "name": "payload_format",
            "required": False,
            "description": "Format for the payload (json, yaml, text)",
            "default": "json",
        },
    ],
    "input_schema": {
        "type": "object",
        "properties": {
            "payload": {
                "type": "object",
                "description": "The payload to be sent via WebSocket",
            },
            "socket_id": {
                "type": "string",
                "description": "Identifier for the WebSocket connection",
            },
        },
        "required": ["payload", "user_properties"],
    },
}


class WebsocketOutput(ComponentBase):
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        self.sockets = None
        self.payload_encoding = self.get_config("payload_encoding")
        self.payload_format = self.get_config("payload_format")

    def invoke(self, message, data):
        if self.sockets is None:
            self.sockets = self.kv_store_get("websocket_connections")
            if self.sockets is None:
                log.error("No WebSocket connections found in KV store")
                self.discard_current_message()
                return None

        try:
            payload = data.get("payload")
            socket_id = data.get("socket_id")

            if not socket_id:
                log.error("No socket_id provided")
                self.discard_current_message()
                return None

            if socket_id not in self.sockets:
                log.error("No active connection found for socket_id: %s", socket_id)
                self.discard_current_message()
                return None

            socket = self.sockets[socket_id]
            encoded_payload = encode_payload(
                payload, self.payload_encoding, self.payload_format
            )
            socket.emit("message", encoded_payload)
            log.debug("Message sent to WebSocket connection %s", socket_id)
        except Exception as e:
            log.error("Error sending message via WebSocket: %s", str(e))
            self.discard_current_message()

        return data
