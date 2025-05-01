"""Base class for OpenAI chat models"""

import uuid
import time

from openai import OpenAI
from ....component_base import ComponentBase
from .....common.message import Message
from .....common.log import log

openai_info_base = {
    "class_name": "OpenAIChatModelBase",
    "description": "Base class for OpenAI chat models",
    "config_parameters": [
        {
            "name": "api_key",
            "required": True,
            "description": "OpenAI API key",
        },
        {
            "name": "model",
            "required": True,
            "description": "OpenAI model to use (e.g., 'gpt-3.5-turbo')",
        },
        {
            "name": "temperature",
            "required": False,
            "description": "Sampling temperature to use",
            "default": 0.7,
        },
        {
            "name": "base_url",
            "required": False,
            "description": "Base URL for OpenAI API",
            "default": None,
        },
        {
            "name": "stream_to_flow",
            "required": False,
            "description": (
                "Name the flow to stream the output to - this must be configured for "
                "llm_mode='stream'. This is mutually exclusive with stream_to_next_component."
            ),
            "default": "",
        },
        {
            "name": "stream_to_next_component",
            "required": False,
            "description": (
                "Whether to stream the output to the next component in the flow. "
                "This is mutually exclusive with stream_to_flow."
            ),
            "default": False,
        },
        {
            "name": "llm_mode",
            "required": False,
            "description": (
                "The mode for streaming results: 'none' or 'stream'. 'stream' "
                "will just stream the results to the named flow. 'none' will "
                "wait for the full response."
            ),
            "default": "none",
        },
        {
            "name": "stream_batch_size",
            "required": False,
            "description": "The minimum number of words in a single streaming result. Default: 15.",
            "default": 15,
        },
        {
            "name": "set_response_uuid_in_user_properties",
            "required": False,
            "description": (
                "Whether to set the response_uuid in the user_properties of the "
                "input_message. This will allow other components to correlate "
                "streaming chunks with the full response."
            ),
            "default": False,
            "type": "boolean",
        },
    ],
    "input_schema": {
        "type": "object",
        "properties": {
            "messages": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "role": {
                            "type": "string",
                            "enum": ["system", "user", "assistant"],
                        },
                        "content": {"type": "string"},
                    },
                    "required": ["role", "content"],
                },
            },
            "stream": {
                "type": "boolean",
                "description": "Whether to stream the response. It is is not provided, it will default to the value of llm_mode.",
                "required": False,
            },
        },
        "required": ["messages"],
    },
    "output_schema": {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "The generated response from the model",
            },
            "chunk": {
                "type": "string",
                "description": "The current chunk of the response",
            },
            "response_uuid": {
                "type": "string",
                "description": "The UUID of the response",
            },
            "first_chunk": {
                "type": "boolean",
                "description": "Whether this is the first chunk of the response",
            },
            "last_chunk": {
                "type": "boolean",
                "description": "Whether this is the last chunk of the response",
            },
            "streaming": {
                "type": "boolean",
                "description": "Whether this is a streaming response",
            },
        },
        "required": ["content"],
    },
}


class OpenAIChatModelBase(ComponentBase):

    def __init__(self, module_info, **kwargs):
        super().__init__(module_info, **kwargs)
        self.init()

    def init(self):
        self.model = self.get_config("model")
        self.temperature = self.get_config("temperature")
        self.stream_to_flow = self.get_config("stream_to_flow")
        self.stream_to_next_component = self.get_config("stream_to_next_component")
        self.llm_mode = self.get_config("llm_mode")
        self.stream_batch_size = self.get_config("stream_batch_size")
        self.set_response_uuid_in_user_properties = self.get_config(
            "set_response_uuid_in_user_properties"
        )
        if self.stream_to_flow and self.stream_to_next_component:
            raise ValueError(
                "stream_to_flow and stream_to_next_component are mutually exclusive"
            ) from None

    def invoke(self, message, data):
        messages = data.get("messages", [])
        stream = data.get("stream", self.llm_mode == "stream")

        client = OpenAI(
            api_key=self.get_config("api_key"), base_url=self.get_config("base_url")
        )

        if stream:
            return self.invoke_stream(client, message, messages)
        else:
            max_retries = 3
            while max_retries > 0:
                try:
                    response = client.chat.completions.create(
                        messages=messages,
                        model=self.model,
                        temperature=self.temperature,
                    )
                    return {"content": response.choices[0].message.content}
                except Exception:
                    log.error("Error invoking OpenAI")
                    max_retries -= 1
                    if max_retries <= 0:
                        raise ValueError("Max retries exceeded") from None
                    else:
                        self.stop_signal.wait(timeout=1)

    def invoke_stream(self, client, message, messages):
        response_uuid = str(uuid.uuid4())
        if self.set_response_uuid_in_user_properties:
            message.set_data("input.user_properties:response_uuid", response_uuid)

        aggregate_result = ""
        current_batch = ""
        first_chunk = True

        max_retries = 3
        while max_retries > 0:
            try:
                for chunk in client.chat.completions.create(
                    messages=messages,
                    model=self.model,
                    temperature=self.temperature,
                    stream=True,
                ):
                    # If we get any response, then don't retry
                    max_retries = 0
                    if chunk.choices[0].delta.content is not None:
                        content = chunk.choices[0].delta.content
                        aggregate_result += content
                        current_batch += content
                        if len(current_batch.split()) >= self.stream_batch_size:
                            if self.stream_to_flow:
                                self.send_streaming_message(
                                    message,
                                    current_batch,
                                    aggregate_result,
                                    response_uuid,
                                    first_chunk,
                                    False,
                                )
                            elif self.stream_to_next_component:
                                self.send_to_next_component(
                                    message,
                                    current_batch,
                                    aggregate_result,
                                    response_uuid,
                                    first_chunk,
                                    False,
                                )
                            current_batch = ""
                            first_chunk = False
            except Exception:
                log.error("Error invoking OpenAI")
                max_retries -= 1
                if max_retries <= 0:
                    raise ValueError("Max retries exceeded") from None
                else:
                    # Small delay before retrying
                    self.stop_signal.wait(timeout=1)

        if self.stream_to_next_component:
            # Just return the last chunk
            return {
                "content": aggregate_result,
                "chunk": current_batch,
                "response_uuid": response_uuid,
                "first_chunk": first_chunk,
                "last_chunk": True,
                "streaming": True,
            }

        if self.stream_to_flow:
            self.send_streaming_message(
                message,
                current_batch,
                aggregate_result,
                response_uuid,
                first_chunk,
                True,
            )

        return {"content": aggregate_result, "response_uuid": response_uuid}

    def send_streaming_message(
        self,
        input_message,
        chunk,
        aggregate_result,
        response_uuid,
        first_chunk=False,
        last_chunk=False,
    ):
        message = Message(
            payload={
                "chunk": chunk,
                "content": aggregate_result,
                "response_uuid": response_uuid,
                "first_chunk": first_chunk,
                "last_chunk": last_chunk,
                "streaming": True,
            },
            user_properties=input_message.get_user_properties(),
        )
        self.send_to_flow(self.stream_to_flow, message)

    def send_to_next_component(
        self,
        input_message,
        chunk,
        aggregate_result,
        response_uuid,
        first_chunk=False,
        last_chunk=False,
    ):
        message = Message(
            payload={
                "chunk": chunk,
                "content": aggregate_result,
                "response_uuid": response_uuid,
                "first_chunk": first_chunk,
                "last_chunk": last_chunk,
                "streaming": True,
            },
            user_properties=input_message.get_user_properties(),
        )

        result = {
            "chunk": chunk,
            "content": aggregate_result,
            "response_uuid": response_uuid,
            "first_chunk": first_chunk,
            "last_chunk": last_chunk,
            "streaming": True,
        }

        self.process_post_invoke(result, message)
