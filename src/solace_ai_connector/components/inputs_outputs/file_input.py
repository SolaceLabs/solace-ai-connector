"""Input file component"""

from copy import deepcopy
from ..component_base import ComponentBase
from ...common.message import Message


class File(ComponentBase):

    def __init__(self, **kwargs):
        super().__init__({}, **kwargs)

    def get_next_message(self):
        # Get the next message from the file

        # Create and return a message object
        return Message(payload="TODO - add implementation")

    def invoke(self, message, data):
        return deepcopy(message.get_payload())
