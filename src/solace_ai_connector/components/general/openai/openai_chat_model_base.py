"""Base class for OpenAI chat models"""

import openai
from ...component_base import ComponentBase

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
                            "enum": ["system", "user", "assistant"]
                        },
                        "content": {
                            "type": "string"
                        }
                    },
                    "required": ["role", "content"]
                }
            }
        },
        "required": ["messages"]
    },
    "output_schema": {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "The generated response from the model"
            }
        },
        "required": ["content"]
    }
}

class OpenAIChatModelBase(ComponentBase):
    def __init__(self, module_info, **kwargs):
        super().__init__(module_info, **kwargs)
        self.init()

    def init(self):
        openai.api_key = self.get_config("api_key")
        self.model = self.get_config("model")
        self.temperature = self.get_config("temperature")

    def invoke(self, message, data):
        messages = data.get("messages", [])
        
        response = openai.ChatCompletion.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature
        )
        
        return {"content": response.choices[0].message['content']}
