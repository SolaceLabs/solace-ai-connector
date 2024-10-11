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
            "socket_id": {
                "type": "string",
                "description": "Identifier for the WebSocket connection",
            },
        },
        "required": ["payload", "user_properties"],
    },
}


# <inst>
# Don't use f-strings for logging, use format directives instead
# </inst>
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
            socket_id = data["socket_id"]

            if socket_id not in self.sockets:
                log.error("No active connection found for socket_id: %s", socket_id)
                self.discard_current_message()
                return None

            socket = self.sockets[socket_id]
            socket.emit("message", json.dumps(payload))
            log.debug("Message sent to WebSocket connection %s", socket_id)
        except Exception as e:
            log.error("Error sending message via WebSocket: %s", str(e))
            self.discard_current_message()

        return data
