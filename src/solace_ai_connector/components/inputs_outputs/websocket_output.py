"""This component sends messages to a websocket connection."""

import json
import threading
from flask import Flask
from flask_socketio import SocketIO
from ...common.log import log
from ...common.message import Message
from ..component_base import ComponentBase

info = {
    "class_name": "WebsocketOutput",
    "description": "Send messages to a websocket connection.",
    "config_parameters": [
        {
            "name": "listen_port",
            "type": "int",
            "required": False,
            "description": "Port to listen on",
            "default": 5001,
        },
    ],
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
                    "connection_id": {
                        "type": "string",
                        "description": "Identifier for the WebSocket connection",
                    },
                },
                "required": ["connection_id"],
            },
        },
        "required": ["payload", "user_properties"],
    },
}

class WebsocketOutput(ComponentBase):
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        self.listen_port = self.get_config("listen_port")
        self.app = Flask(__name__)
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        self.thread = None
        self.connections = {}
        self.setup_websocket()

    def setup_websocket(self):
        @self.socketio.on('connect')
        def handle_connect():
            connection_id = self.socketio.sid
            self.connections[connection_id] = self.socketio
            log.info(f"New WebSocket connection established. Connection ID: {connection_id}")

        @self.socketio.on('disconnect')
        def handle_disconnect():
            connection_id = self.socketio.sid
            if connection_id in self.connections:
                del self.connections[connection_id]
                log.info(f"WebSocket connection closed. Connection ID: {connection_id}")

    def start(self):
        if not self.thread:
            self.thread = threading.Thread(target=self.run_websocket)
            self.thread.start()

    def run_websocket(self):
        self.socketio.run(self.app, port=self.listen_port)

    def stop_component(self):
        if self.thread:
            self.socketio.stop()
            self.thread.join()
            self.thread = None

    def invoke(self, message, data):
        return data

    def send_message(self, message: Message):
        try:
            payload = message.get_payload()
            user_properties = message.get_user_properties()
            connection_id = user_properties.get('connection_id')

            if not connection_id:
                log.error("No connection_id found in user_properties")
                return

            if connection_id not in self.connections:
                log.error(f"No active connection found for connection_id: {connection_id}")
                return

            socket = self.connections[connection_id]
            socket.emit('message', json.dumps(payload))
            log.debug(f"Message sent to WebSocket connection {connection_id}")
        except Exception as e:
            log.error(f"Error sending message via WebSocket: {str(e)}")
