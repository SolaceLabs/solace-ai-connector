# A simple pass-through component - what goes in comes out

from ..component_base import ComponentBase


info = {
    "class_name": "PassThrough",
    "description": "What goes in comes out",
    "config_parameters": [],
    "input_schema": {
        "type": "object",
        "properties": {},
    },
    "output_schema": {
        "type": "object",
        "properties": {},
    },
}


class PassThrough(ComponentBase):
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)

    def invoke(self, message, data):
        if data is None:
            return {}
        return data
