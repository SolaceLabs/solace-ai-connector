"""Base class for OpenAI chat models"""

from copy import deepcopy
from ...langchain.langchain_chat_model_base import (
    LangChainChatModelBase,
    info_base,
)

openai_info_base = deepcopy(info_base)
openai_info_base["config_parameters"].extend([
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
])

class OpenAIChatModelBase(LangChainChatModelBase):
    def __init__(self, module_info, **kwargs):
        super().__init__(module_info, **kwargs)
        
    def init(self):
        from langchain_openai import ChatOpenAI
        
        self.component = ChatOpenAI(
            openai_api_key=self.get_config("api_key"),
            model_name=self.get_config("model"),
            temperature=self.get_config("temperature"),
        )
