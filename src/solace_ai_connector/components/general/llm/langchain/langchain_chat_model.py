# This is a wrapper around all the LangChain chat models
# The configuration will control dynamic loading of the chat models
from copy import deepcopy
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
        self, input_message, messages, session_id=None, clear_history=False
    ):
        return self.component.invoke(messages)
