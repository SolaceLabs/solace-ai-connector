"""This component sends messages to a websocket connection."""

import json
from ...common.log import log
from ...common.message import Message
from ..component_base import ComponentBase

info = {
    "class_name": "WebsocketOutput",
    "description": "Send messages to a websocket connection.",
    "config_parameters": [],
    "input_schema": {
        "type": "object",
        "properties": {
            "payload": {
                "type": "object",
                "description": "The payload to be sent via WebSocket",
            },
            "user_properties": {
                "type": "object",
                "properties": {
                    "socket_id": {
                        "type": "string",
                        "description": "Identifier for the WebSocket connection",
                    },
                },
                "required": ["socket_id"],
            },
        },
        "required": ["payload", "user_properties"],
    },
}

class WebsocketOutput(ComponentBase):
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        self.sockets = None

    def invoke(self, message, data):
        if self.sockets is None:
            self.sockets = self.kv_store_get("websocket_connections")
            if self.sockets is None:
                log.error("No WebSocket connections found in KV store")
                self.discard_current_message()
                return None

        try:
            payload = data["payload"]
            socket_id = data["user_properties"]["socket_id"]

            if socket_id not in self.sockets:
                log.error(f"No active connection found for socket_id: {socket_id}")
                self.discard_current_message()
                return None

            socket = self.sockets[socket_id]
            socket.emit('message', json.dumps(payload))
            log.debug(f"Message sent to WebSocket connection {socket_id}")
        except Exception as e:
            log.error(f"Error sending message via WebSocket: {str(e)}")
            self.discard_current_message()

        return data

    def send_message(self, message: Message):
        self.invoke(message, {
            "payload": message.get_payload(),
            "user_properties": message.get_user_properties()
        })
