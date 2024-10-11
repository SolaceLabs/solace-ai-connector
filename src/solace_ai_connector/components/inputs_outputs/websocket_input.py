"""This component receives messages from a websocket connection and sends them to the next component in the flow."""

import json
import threading
import uuid
from flask import Flask
from flask_socketio import SocketIO
from ...common.log import log
from ...common.message import Message
from ...common.event import Event, EventType
from ..component_base import ComponentBase

info = {
    "class_name": "WebsocketInput",
    "description": "Listen for incoming messages on a websocket connection.",
    "config_parameters": [
        {
            "name": "listen_port",
            "type": "int",
            "required": False,
            "description": "Port to listen on",
            "default": 5000,
        },
    ],
    "output_schema": {
        "type": "object",
        "properties": {
            "payload": {
                "type": "object",
                "description": "The decoded JSON payload received from the WebSocket",
            },
        },
        "required": ["payload"],
    },
}

class WebsocketInput(ComponentBase):
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        self.listen_port = self.get_config("listen_port")
        self.app = Flask(__name__)
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        self.thread = None
        self.sockets = {}
        self.setup_websocket()

    def setup_websocket(self):
        @self.socketio.on("connect")
        def handle_connect():
            socket_id = str(uuid.uuid4())
            self.sockets[socket_id] = self.socketio
            self.kv_store_set("websocket_connections", self.sockets)
            log.info(f"New WebSocket connection established. Socket ID: {socket_id}")
            return socket_id

        @self.socketio.on("disconnect")
        def handle_disconnect():
            socket_id = self.socketio.sid
            if socket_id in self.sockets:
                del self.sockets[socket_id]
                self.kv_store_set("websocket_connections", self.sockets)
                log.info(f"WebSocket connection closed. Socket ID: {socket_id}")

        @self.socketio.on("message")
        def handle_message(data):
            try:
                payload = json.loads(data)
                socket_id = self.socketio.sid
                message = Message(payload=payload, user_properties={"socket_id": socket_id})
                event = Event(EventType.MESSAGE, message)
                self.enqueue(event)
            except json.JSONDecodeError:
                log.error(f"Received invalid JSON: {data}")

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
        try:
            return {
                "payload": message.get_payload(),
                "topic": message.get_topic(),
                "user_properties": message.get_user_properties()
            }
        except Exception as e:
            log.error(f"Error processing WebSocket message: {str(e)}")
            return None

    def get_next_message(self):
        return self.get_input_queue().get()
