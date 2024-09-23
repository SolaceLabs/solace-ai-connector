# A simple pass-through component - what goes in comes out

import sys

sys.path.append("src")

from solace_ai_connector.components.component_base import ComponentBase
from solace_ai_connector.common.message import Message


info = {
    "class_name": "LlmStreamingCustomComponent",
    "description": "Do a blocking LLM request/response",
    "config_parameters": [
        {
            "name": "llm_request_topic",
            "description": "The topic to send the request to",
            "type": "string",
        }
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


class LlmStreamingCustomComponent(ComponentBase):
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        self.llm_request_topic = self.get_config("llm_request_topic")

    def invoke(self, message, data):
        llm_message = Message(payload=data, topic=self.llm_request_topic)
        for message, last_message in self.do_broker_request_response(
            llm_message,
            stream=True,
            streaming_complete_expression="input.payload:last_chunk",
        ):
            text = message.get_data("input.payload:chunk")
            if not text:
                text = message.get_data("input.payload:content") or "no response"
            if last_message:
                return {"chunk": text}
            self.output_streaming(message, {"chunk": text})

    def output_streaming(self, message, data):
        return self.process_post_invoke(data, message)
