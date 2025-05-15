"""An input component that specifies that it needs a nack when the message has finished 
processing. This is used to test the nack functionality of the connector. 
This component is used in the tests."""

from ...component_base import ComponentBase
from ....common import Message_NACK_Outcome


info = {
    "class_name": "NeedNackInput",
    "description": (
        "An input component that specifies that it needs a nack when the message has finished "
    ),
    "config_parameters": [
        {
            "name": "nack_message",
            "required": False,
            "description": "The text to go along with the exception raised when nacked",
            "type": "string",
            "default": "negative acknowledgement called",
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


class NeedNackInput(ComponentBase):

    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        self.need_negative_acknowledgement = True

    def invoke(self, message, data):
        # Add the negative acknowledgement callback to the message
        callback = self.get_negative_acknowledgement_callback()
        if callback is not None:
            message.add_negative_acknowledgements(callback)
        return {}

    def get_negative_acknowledgement_callback(self):
        return lambda nack: self.negative_acknowledge_message(nack)

    def negative_acknowledge_message(self, nack):
        # Raise an exception so the test can verify that the nack was called
        raise Exception(  # pylint: disable=broad-exception-raised
            f"{self.get_config('nack_message')} with outcome {nack}"
        ) from None

    def nack_reaction_to_exception(self, exception_type):
        """Determine NACK reaction based on the exception type."""
        return Message_NACK_Outcome.REJECTED
