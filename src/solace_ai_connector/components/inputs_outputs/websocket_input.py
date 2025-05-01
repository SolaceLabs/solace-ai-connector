"""This component receives messages from a websocket connection and sends them to the next component in the flow."""

import json
import os
import copy

from flask import request
from ...common.log import log
from ...common.message import Message
from ...common.event import Event, EventType
from ...common.utils import decode_payload
from .websocket_base import WebsocketBase, base_info


# Merge base_info into info
info = copy.deepcopy(base_info)
info.update(
    {
        "class_name": "WebsocketInput",
        "description": "Listen for incoming messages on a websocket connection.",
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
)


class WebsocketInput(WebsocketBase):

    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        self.payload_encoding = self.get_config("payload_encoding")
        self.payload_format = self.get_config("payload_format")

        if not self.listen_port:
            raise ValueError("listen_port is required for WebsocketInput") from None

        if not os.path.isabs(self.html_path):
            self.html_path = os.path.join(os.getcwd(), self.html_path)

        self.setup_message_handler()

    def setup_message_handler(self):
        @self.socketio.on("message")
        def handle_message(data):
            try:
                decoded_payload = decode_payload(
                    data, self.payload_encoding, self.payload_format
                )
                socket_id = request.sid
                message = Message(
                    payload=decoded_payload, user_properties={"socket_id": socket_id}
                )
                event = Event(EventType.MESSAGE, message)
                self.process_event_with_tracing(event)
            except json.JSONDecodeError:
                log.error("Received invalid payload.")
            except AssertionError as e:
                raise AssertionError(
                    "Error Payload format. Please check the payload format."
                ) from None
            except Exception as e:
                self.handle_component_error(e, event)

    def run(self):
        self.run_server()

    def stop_component(self):
        self.stop_server()

    def invoke(self, message, data):
        try:
            return {
                "payload": message.get_payload(),
                "topic": message.get_topic(),
                "user_properties": message.get_user_properties(),
            }
        except Exception:
            log.error("Error processing WebSocket message.")
            return None
