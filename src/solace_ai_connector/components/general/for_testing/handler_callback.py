"""This test component allows a tester to configure callback handlers for
 get_next_event, send_message and invoke methods"""

from ...component_base import ComponentBase


info = {
    "class_name": "HandlerCallback",
    "description": (
        "This test component allows a tester to configure callback handlers for "
        "get_next_event, send_message and invoke methods"
    ),
    "config_parameters": [
        {
            "name": "get_next_event_handler",
            "required": False,
            "description": "The callback handler for the get_next_event method",
            "type": "function",
        },
        {
            "name": "send_message_handler",
            "required": False,
            "description": "The callback handler for the send_message method",
            "type": "function",
        },
        {
            "name": "invoke_handler",
            "required": False,
            "description": "The callback handler for the invoke method",
            "type": "function",
        },
    ],
    "input_schema": {
        "type": "object",
        "properties": {},
    },
    "output_schema": {
        "type": "object",
        "properties": {},
    },
}


class HandlerCallback(ComponentBase):
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        self.get_next_event_handler = self.get_config("get_next_event_handler")
        self.send_message_handler = self.get_config("send_message_handler")
        self.invoke_handler = self.get_config("invoke_handler")

    def get_next_event(self):
        if self.get_next_event_handler:
            return self.get_next_event_handler(self)
        else:
            return super().get_next_event()

    def send_message(self, message):
        if self.send_message_handler:
            return self.send_message_handler(self, message)
        else:
            return super().send_message(message)

    def invoke(self, message, data):
        if self.invoke_handler:
            return self.invoke_handler(self, message, data)
        else:
            return super().invoke(message, data)
