"""Test component to nack the message when it is processed"""

from ...component_base import ComponentBase
from ....common import Message_NACK_Outcome
from ....common.event import Event, EventType


info = {
    "class_name": "GiveNackOutput",
    "description": ("A component that will nack the message when it is processed. "),
    "config_parameters": [
        {
            "name": "nack_outcome",
            "required": False,
            "description": "The outcome to use for the nack (FAILED or REJECTED)",
            "type": "string",
            "default": "REJECTED",
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


class GiveNackOutput(ComponentBase):

    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)

    def invoke(self, message, data):
        try:
            nack_outcome = self.get_config("nack_outcome")
            if nack_outcome == "FAILED":
                message.call_negative_acknowledgements(Message_NACK_Outcome.FAILED)
            else:
                message.call_negative_acknowledgements(Message_NACK_Outcome.REJECTED)
            return data
        except Exception as e:
            # This will catch the exception raised by the negative acknowledgement callback
            # and put it in the error queue
            self.handle_error(e, Event(EventType.MESSAGE, message))
            raise

    def get_negative_acknowledgement_callback(self):
        """Return None as this component doesn't need to be NACKed."""
        return None

    def nack_reaction_to_exception(self, exception_type):
        """Determine NACK reaction based on the exception type."""
        nack_outcome = self.get_config("nack_outcome")
        if nack_outcome == "FAILED":
            return Message_NACK_Outcome.FAILED
        return Message_NACK_Outcome.REJECTED
