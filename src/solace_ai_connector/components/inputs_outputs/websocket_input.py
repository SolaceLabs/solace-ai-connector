"""This component receives messages from a websocket connection and sends them to the next component in the flow."""

import json
import threading
import uuid
import os

from flask import Flask, send_file, request
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
        {
            "name": "serve_html",
            "type": "bool",
            "required": False,
            "description": "Serve the example HTML file",
            "default": False,
        },
        {
            "name": "html_path",
            "type": "string",
            "required": False,
            "description": "Path to the HTML file to serve",
            "default": "examples/websocket/websocket_example_app.html",
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
        self.serve_html = self.get_config("serve_html")
        self.html_path = self.get_config("html_path")
        self.app = Flask(__name__)
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        self.sockets = {}
        self.kv_store_set("websocket_connections", self.sockets)
        self.setup_websocket()

        if self.serve_html:
            self.setup_html_route()
            # Fix the path to the HTML file - if it's relative, it
            # should be relative to the current working directory
            if not os.path.isabs(self.html_path):
                self.html_path = os.path.join(os.getcwd(), self.html_path)

    def setup_html_route(self):
        @self.app.route("/")
        def serve_html():
            # Get the directory where this app is running
            directory = os.path.dirname(os.path.realpath(__file__))
            print(directory)
            return send_file(self.html_path)

    def setup_websocket(self):
        @self.socketio.on("connect")
        def handle_connect():
            socket_id = str(uuid.uuid4())
            self.sockets[socket_id] = self.socketio
            self.kv_store_set("websocket_connections", self.sockets)
            log.info("New WebSocket connection established. Socket ID: %s", socket_id)
            return socket_id

        @self.socketio.on("disconnect")
        def handle_disconnect():
            socket_id = request.sid
            if socket_id in self.sockets:
                del self.sockets[socket_id]
                self.kv_store_set("websocket_connections", self.sockets)
                log.info("WebSocket connection closed. Socket ID: %s", socket_id)

        @self.socketio.on("message")
        def handle_message(data):
            try:
                payload = json.loads(data)
                socket_id = request.sid
                message = Message(
                    payload=payload, user_properties={"socket_id": socket_id}
                )
                event = Event(EventType.MESSAGE, message)
                self.enqueue(event)
            except json.JSONDecodeError:
                log.error("Received invalid JSON: %s", data)

    def run(self):
        self.socketio.run(self.app, port=self.listen_port)

    def stop_component(self):
        if self.socketio:
            self.socketio.stop()

    def invoke(self, message, data):
        try:
            return {
                "payload": message.get_payload(),
                "topic": message.get_topic(),
                "user_properties": message.get_user_properties(),
            }
        except Exception as e:
            log.error("Error processing WebSocket message: %s", str(e))
            return None
