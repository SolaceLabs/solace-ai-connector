"""This component receives messages from a websocket connection and sends them to the next component in the flow."""

from ...common.log import log
from ...common.message import Message

info = {
    "class_name": "WebsocketInput",
    "description": ("Listent for incoming messages on a websocket connection. "),
    "config_parameters": [
        {
            "name": "listen_port",
            "type": "int",
            "required": False,
            "description": "Port to listen on",
            "default": "5000",
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


class HttpServerInputBase(ComponentBase):
    def __init__(self, receiver_class, **kwargs):
        super().__init__(info, **kwargs)
        self.receiver_queue = None
        self.receiver = None
        self.init_receiver(receiver_class)

    def init_receiver(self, receiver_class):
        self.receiver_queue = queue.Queue()
        self.stop_receiver_event = threading.Event()
        self.receiver = receiver_class(
            server_input=self,
            input_queue=self.receiver_queue,
            stop_event=self.stop_receiver_event,
            listen_port=self.get_config("listen_port"),
        )
        self.receiver.start()

    def stop_component(self):
        self.stop_receiver()

    def stop_receiver(self):
        self.stop_receiver_event.set()
        self.receiver.join()

    def get_next_event(self):
        message = self.receiver_queue.get()
        return Event(EventType.MESSAGE, message)

    def invoke(self, _message, data):
        return data


class HttpServerReceiver(threading.Thread):
    def __init__(
        self,
        server_input,
        input_queue,
        stop_event,
        listen_port=5000,
        acknowledgement_message=None,
    ):
        threading.Thread.__init__(self)
        self.server_input = server_input
        self.input_queue = input_queue
        self.stop_event = stop_event
        self.listen_port = listen_port
        self.acknowledgement_message = acknowledgement_message
        self.app = None
        self.init_app()

    def init_app(self):
        from flask import Flask
        from flask_cors import CORS

        self.app = Flask(__name__)
        CORS(self.app)
        self.register_routes()

    def run(self):
        self.app.run(port=self.listen_port)
        self.stop_event.wait()

    def handle_event(self, server_input_id, event):
        payload = {
            "text": event.get("message", ""),
            "user_id": event.get("user_id", "default@example.com"),
            "timestamp": event.get("timestamp", ""),
        }
        user_properties = {
            "server_input_id": server_input_id,
            "user_id": event.get("user_id", ""),
            "timestamp": event.get("timestamp", ""),
            "input_type": "web",
            "use_history": False,
        }

        message = Message(payload=payload, user_properties=user_properties)
        message.set_previous(payload)
        self.input_queue.put(message)

        return (
            self.acknowledgement_message
            if self.acknowledgement_message
            else "Message received"
        )

    def register_routes(self):
        # This method should be implemented by child classes
        pass

    def generate_stream_response(self, server_input_id, event, response_queue):
        # This method should be implemented by child classes
        pass

    def generate_simple_response(self, server_input_id, event, response_queue):
        # This method should be implemented by child classes
        pass
