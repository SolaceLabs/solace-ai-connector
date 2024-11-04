"""LiteLLM chat model component"""

from .litellm_chat_model_base import LiteLLMChatModelBase, litellm_chat_info_base

info = litellm_chat_info_base.copy()
info["class_name"] = "LiteLLMChatModel"
info["description"] = "LiteLLM chat component"

class LiteLLMChatModel(LiteLLMChatModelBase):
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
