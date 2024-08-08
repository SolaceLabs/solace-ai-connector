"""OpenAI chat model component"""

from .openai_chat_model_base import OpenAIChatModelBase, openai_info_base

info = openai_info_base.copy()
info["class_name"] = "OpenAIChatModel"
info["description"] = "OpenAI chat model component"

class OpenAIChatModel(OpenAIChatModelBase):
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
