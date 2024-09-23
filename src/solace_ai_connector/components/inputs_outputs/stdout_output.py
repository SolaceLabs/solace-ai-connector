# An output component to print to STDOUT

import yaml  # pylint: disable=import-error
from ..component_base import ComponentBase

info = {
    "class_name": "Stdout",
    "description": "STDOUT output component",
    "config_parameters": [
        {
            "name": "add_new_line_between_messages",
            "required": False,
            "description": "Add a new line between messages",
            "type": "boolean",
            "default": True,
        }
    ],
    "input_schema": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
            },
        },
        "required": ["text"],
    },
}


class Stdout(ComponentBase):
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        self.add_newline = self.get_config("add_new_line_between_messages")

    def invoke(self, message, data):
        # Print the message to STDOUT
        if isinstance(data, dict) or isinstance(data, list):
            print(yaml.dump(data))
        else:
            print(data, end="")
            if self.add_newline:
                print()

        return data
