# An input component that reads from STDIN

from copy import deepcopy
from solace_ai_event_connector.flow_components.component_base import ComponentBase
from solace_ai_event_connector.common.message import Message


info = {
    "class_name": "Stdin",
    "description": (
        "STDIN input component. The component will prompt for "
        "input, which will then be placed in the message payload using the output schema below."
    ),
    "config_parameters": [],
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
    def get_next_message(self):
        # Get the next message from STDIN
        obj = {"text": input(self.config.get("prompt", "Enter text: "))}

        # Create and return a message object
        return Message(payload=obj)

    # def get_input_data(self, message):
    #     return message.payload

    def invoke(self, message, data):
        return deepcopy(message.get_payload())
