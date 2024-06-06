# An output component to print to STDOUT

import yaml  # pylint: disable=import-error
from ..component_base import ComponentBase

info = {
    "class_name": "Stdout",
    "description": "STDOUT output component",
    "config_parameters": [],
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

    def invoke(self, message, data):
        # Print the message to STDOUT
        print(yaml.dump(data))
        return data
