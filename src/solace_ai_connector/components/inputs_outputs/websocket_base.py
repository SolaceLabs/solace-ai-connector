"""Base class for WebSocket components."""

import os
import signal
from abc import ABC, abstractmethod
from flask import Flask, send_file, request
from flask_socketio import SocketIO
from ...common.log import log
from ..component_base import ComponentBase
from flask.logging import default_handler

base_info = {
    "config_parameters": [
        {
            "name": "listen_port",
            "type": "int",
            "required": False,
            "description": "Port to listen on (optional)",
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
}


class WebsocketBase(ComponentBase, ABC):
    def __init__(self, info, **kwargs):
        super().__init__(info, **kwargs)
        self.listen_port = self.get_config("listen_port")
        self.serve_html = self.get_config("serve_html", False)
        self.html_path = self.get_config("html_path", "")
        self.sockets = {}
        self.app = None
        self.socketio = None

        if self.listen_port:
            self.setup_websocket_server()

    def setup_websocket_server(self):
        self.app = Flask(__name__)

        # Enable Flask debugging
        self.app.debug = False

        # Set up Flask logging
        # self.app.logger.setLevel(logging.DEBUG)
        # self.app.logger.addHandler(default_handler)

        # Enable SocketIO logging
        # logging.getLogger("socketio").setLevel(logging.DEBUG)
        # logging.getLogger("engineio").setLevel(logging.DEBUG)

        self.socketio = SocketIO(
            self.app, cors_allowed_origins="*", logger=False, engineio_logger=False
        )
        self.setup_websocket()

        if self.serve_html:
            self.setup_html_route()

    def setup_html_route(self):
        @self.app.route("/")
        def serve_html():
            return send_file(self.html_path)

    def setup_websocket(self):
        @self.socketio.on("connect")
        def handle_connect():
            socket_id = request.sid
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

    def run_server(self):
        if self.socketio:
            self.socketio.run(
                self.app, port=self.listen_port, debug=False, use_reloader=False
            )

    def stop_server(self):
        try:
            func = request.environ.get('werkzeug.server.shutdown')
            if func is None:
                raise RuntimeError('Not running with the Werkzeug Server')
            func()
        except RuntimeError:
            # Ignore the error if the server is already shutdown
            pass
        try:
            self.socketio.stop()
        except Exception as e:
            pass
        # force exiting component
        os.kill(os.getpid(), signal.SIGINT)
 
    def get_sockets(self):
        if not self.sockets:
            self.sockets = self.kv_store_get("websocket_connections") or {}
        return self.sockets

    def send_to_socket(self, socket_id, payload):
        sockets = self.get_sockets()
        if socket_id == "*":
            for socket in sockets.values():
                socket.emit("message", payload)
            log.debug("Message sent to all WebSocket connections")
        elif socket_id in sockets:
            sockets[socket_id].emit("message", payload)
            log.debug("Message sent to WebSocket connection %s", socket_id)
        else:
            log.error("No active connection found for socket_id: %s", socket_id)
            return False
        return True

    @abstractmethod
    def invoke(self, message, data):
        pass
