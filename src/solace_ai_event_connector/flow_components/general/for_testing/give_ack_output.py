"""Test component to ack the message when it is processed"""

from solace_ai_event_connector.flow_components.component_base import ComponentBase


info = {
    "class_name": "GiveAckOutput",
    "description": ("A component that will ack the message when it is processed. "),
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


class GiveAckOutput(ComponentBase):
    def invoke(self, message, data):
        message.call_acknowledgements()
        return data
