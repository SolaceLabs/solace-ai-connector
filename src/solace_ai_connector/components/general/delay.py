"""A simple component that simply passes the input to the output, but with a configurable delay"""

from copy import deepcopy
from time import sleep
from ..component_base import ComponentBase


info = {
    "class_name": "Delay",
    "description": (
        "A simple component that simply passes the input "
        "to the output, but with a configurable delay. "
        "Note that it will not service the next input until the delay has passed. "
        "If this component has num_instances > 1, each instance will run in parallel. "
    ),
    "short_description": "A simple component that simply passes the input to the output, but with a configurable delay.",
    "config_parameters": [
        {
            "name": "delay",
            "description": "The delay in seconds",
            "type": "number",
            "default": 1,
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


class Delay(ComponentBase):
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)

    def invoke(self, message, data):
        delay = self.get_config("delay")
        sleep(delay)
        return deepcopy(data)
