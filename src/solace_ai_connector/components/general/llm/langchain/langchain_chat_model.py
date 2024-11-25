# This is a wrapper around all the LangChain chat models
# The configuration will control dynamic loading of the chat models
from uuid import uuid4
from copy import deepcopy
from collections import namedtuple
from .langchain_chat_model_base import (
    LangChainChatModelBase,
    info_base,
)

# Deepcopy info_base
info = deepcopy(info_base)
info["class_name"] = "LangChainChatModel"


class LangChainChatModel(LangChainChatModelBase):

    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)

    def invoke_model(
        self,
        input_message,
        messages,
        session_id=None,
        clear_history=False,
        stream=False,
    ):
        if not stream:
            return self.component.invoke(messages)

        aggregate_result = ""
        current_batch = ""
        response_uuid = str(uuid4())
        first_chunk = True

        for chunk in self.component.stream(messages):
            aggregate_result += chunk.content
            current_batch += chunk.content
            if len(current_batch) >= self.stream_batch_size:
                if self.stream_to_flow:
                    self.send_streaming_message(
                        input_message,
                        current_batch,
                        aggregate_result,
                        response_uuid,
                        first_chunk,
                    )
                current_batch = ""
                first_chunk = False

        if self.stream_to_flow:
            self.send_streaming_message(
                input_message,
                current_batch,
                aggregate_result,
                response_uuid,
                first_chunk,
                True,
            )

        result = namedtuple("Result", ["content", "response_uuid"])(
            aggregate_result, response_uuid
        )

        return result
