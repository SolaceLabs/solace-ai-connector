"""LiteLLM chat model component"""

import uuid
from .litellm_base import LiteLLMBase
from .litellm_base import litellm_info_base
from .....common.message import Message
from .....common.log import log

litellm_chat_info_base = litellm_info_base.copy()
litellm_chat_info_base.update(
    {
        "class_name": "LiteLLMChatModelBase",
        "description": "LiteLLM chat model base component",
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
                    "description": "Whether to stream the response - overwrites llm_mode",
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
    },
)
litellm_chat_info_base["config_parameters"].extend(
    [
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
    ]
)


class LiteLLMChatModelBase(LiteLLMBase):

    def __init__(self, info, **kwargs):
        super().__init__(info, **kwargs)
        self.stream_to_flow = self.get_config("stream_to_flow")
        self.stream_to_next_component = self.get_config("stream_to_next_component")
        self.llm_mode = self.get_config("llm_mode")
        self.stream_batch_size = self.get_config("stream_batch_size")

        if self.stream_to_flow and self.stream_to_next_component:
            raise ValueError(
                "stream_to_flow and stream_to_next_component are mutually exclusive"
            )

    def invoke(self, message, data):
        """invoke the model"""
        messages = data.get("messages", [])
        stream = data.get("stream", self.llm_mode == "stream")

        if stream:
            return self.invoke_stream(message, messages)
        else:
            return self.invoke_non_stream(messages)

    def invoke_non_stream(self, messages):
        """invoke the model without streaming"""
        try:
            response = self.load_balance(messages, stream=False)
            return {"content": response.choices[0].message.content}
        except Exception as e:
            log.error("Error invoking LiteLLM: %s", e)
            raise e

    def invoke_stream(self, message, messages):
        """invoke the model with streaming"""
        response_uuid = str(uuid.uuid4())
        if self.set_response_uuid_in_user_properties:
            message.set_data("input.user_properties:response_uuid", response_uuid)

        aggregate_result = ""
        current_batch = ""
        first_chunk = True

        try:
            response = self.load_balance(messages, stream=True)

            for chunk in response:
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
        except Exception as e:
            log.error("Error invoking LiteLLM: %s", e)
            raise e

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
