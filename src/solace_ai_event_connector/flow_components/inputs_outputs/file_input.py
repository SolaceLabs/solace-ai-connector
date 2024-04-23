"""Input file component"""

from copy import deepcopy
from solace_ai_event_connector.common.log import log
from solace_ai_event_connector.flow_components.component_base import ComponentBase
from solace_ai_event_connector.common.message import Message


class File(ComponentBase):
    def __init__(self, config, index):
        super().__init__(config, index)
        log.debug("Creating component %s", self.name)

    def get_next_message(self):
        # Get the next message from the file

        # Create and return a message object
        return Message(payload="TODO - add implementation")

    def invoke(self, message, data):
        return deepcopy(message.get_payload())
