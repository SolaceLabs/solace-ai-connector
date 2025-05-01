"""An input component that specifies that it needs an ack when the message has finished 
processing. This is used to test the ack functionality of the connector. 
This component is used in the tests."""

from ...component_base import ComponentBase


info = {
    "class_name": "NeedAckInput",
    "description": (
        "An input component that specifies that it needs an ack when the message has finished "
    ),
    "config_parameters": [
        {
            "name": "ack_message",
            "required": False,
            "description": "The text to go along with the exception raised when acked",
            "type": "string",
            "default": "acknowledgement called",
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


class NeedAckInput(ComponentBase):

    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        self.need_acknowledgement = True

    def invoke(self, message, data):
        return {}

    def get_acknowledgement_callback(self):
        return lambda: self.acknowledge_message()  # pylint: disable=unnecessary-lambda

    def acknowledge_message(self):
        # Raise an exception so the test can verify that the ack was called
        raise Exception(  # pylint: disable=broad-exception-raised
            self.get_config("ack_message")
        ) from None
