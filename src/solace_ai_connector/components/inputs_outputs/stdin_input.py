# An input component that reads from STDIN

import threading

from copy import deepcopy
from ..component_base import ComponentBase
from ...common.message import Message


info = {
    "class_name": "Stdin",
    "description": (
        "STDIN input component. The component will prompt for "
        "input, which will then be placed in the message payload using the output schema below. "
        "The component will wait for its output message to be acknowledged before prompting for "
        "the next input."
    ),
    "config_parameters": [
        {
            "name": "prompt",
            "required": False,
            "description": "The prompt to display when asking for input",
        }
    ],
    "output_schema": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
            },
        },
        "required": ["text"],
    },
}


class Stdin(ComponentBase):
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        self.need_acknowledgement = True
        self.next_input_signal = threading.Event()
        self.next_input_signal.set()

    def get_next_message(self):
        # Wait for the next input signal
        self.next_input_signal.wait()

        # Reset the event for the next use
        self.next_input_signal.clear()

        # Get the next message from STDIN
        obj = {"text": input(self.config.get("prompt", "\nEnter text: "))}

        # Create and return a message object
        return Message(payload=obj)

    def invoke(self, message, data):
        return deepcopy(message.get_payload())

    def acknowledge_message(self):
        self.next_input_signal.set()

    def get_acknowledgement_callback(self):
        return self.acknowledge_message
