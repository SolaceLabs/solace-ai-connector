"""OpenAI chat model component"""

from copy import deepcopy
from .openai_chat_model_base import OpenAIChatModelBase, openai_info_base

info = deepcopy(openai_info_base)
info["class_name"] = "OpenAIChatModel"
info["description"] = "OpenAI chat model component"

class OpenAIChatModel(OpenAIChatModelBase):
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)

    def invoke_model(self, input_message, messages, session_id=None, clear_history=False):
        return self.component.invoke(messages)
