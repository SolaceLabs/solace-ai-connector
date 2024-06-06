"""A simple component that simply passes the input to the output, but with a configurable delay"""

from ...component_base import ComponentBase


info = {
    "class_name": "Fail",
    "description": (
        "A component that will raise the specified exception each time it receives a message. "
        "This is useful for testing error handling."
    ),
    "config_parameters": [
        {
            "name": "error_message",
            "required": True,
            "description": "The message to raise",
            "type": "string",
        },
        {
            "name": "exception_type",
            "required": False,
            "description": "The type of exception to raise",
            "type": "string",
            "default": "ValueError",
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


class Fail(ComponentBase):
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)

    def invoke(self, message, data):
        error_message = self.get_config("error_message")
        exception_type = self.get_config("exception_type")
        exception = __builtins__[exception_type]
        raise exception(error_message)
