# This is the base class of a wrapper around all the LangChain chat models
# The configuration will control dynamic loading of the chat models

import yaml
from abc import abstractmethod
from langchain_core.output_parsers import JsonOutputParser

from ....common.utils import get_obj_text
from langchain.schema.messages import (
    HumanMessage,
    SystemMessage,
    AIMessage,
    FunctionMessage,
    ChatMessage,
)

from .langchain_base import (
    LangChainBase,
)


info_base = {
    "class_name": "<override>",
    "description": "Provide access to all the LangChain chat models via configuration",
    "config_parameters": [
        {
            "name": "langchain_module",
            "required": True,
            "description": "The chat model module - e.g. 'langchain_openai.chat_models'",
        },
        {
            "name": "langchain_class",
            "required": True,
            "description": "The chat model class to use - e.g. ChatOpenAI",
        },
        {
            "name": "langchain_component_config",
            "required": True,
            "description": "Model specific configuration for the chat model. "
            "See documentation for valid parameter names.",
        },
        {
            "name": "llm_response_format",
            "required": False,
            "description": (
                "The response format for this LLM request. This can be "
                "'json', 'yaml', or 'text'. If set to 'json' or 'yaml', the response "
                "will be parsed by the appropriate parser and the fields will be "
                "available in the response object. If set to 'text', the response will "
                "be returned as a string."
            ),
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
                            "description": "The role of the LLM message (user, assistant, system)",
                        },
                        "content": {
                            "type": "string",
                            "description": "The content of the LLM message",
                        },
                    },
                    "required": ["content"],
                },
            },
        },
        "required": ["messages"],
    },
    "output_schema": {
        "type": "object",
        "properties": {"result": {"type": "string"}},
        "required": ["result"],
        "description": (
            "The result of the chat model invocation. If a format "
            "is specified, then the result text will be parsed and "
            "the fields will be available in the response object."
        ),
    },
}


class LangChainChatModelBase(LangChainBase):
    def invoke(self, message, data):
        messages = []

        for item in data["messages"]:
            if item["role"] == "system":
                messages.append(SystemMessage(content=item["content"]))
            elif item["role"] == "user" or item["role"] == "human":
                messages.append(HumanMessage(content=item["content"]))
            elif item["role"] == "assistant" or item["role"] == "bot":
                messages.append(AIMessage(content=item["content"]))
            elif item["role"] == "function":
                messages.append(FunctionMessage(content=item["content"]))
            elif item["role"] == "chat":
                messages.append(ChatMessage(content=item["content"]))
            else:
                raise ValueError(
                    f"Invalid message role for Chat Model invocation: {item['role']}"
                )

        session_id = data.get("session_id", None)
        clear_history = data.get("clear_history", False)

        llm_res = self.invoke_model(
            message, messages, session_id=session_id, clear_history=clear_history
        )

        res_format = self.get_config("llm_response_format", "text")
        if res_format == "json":
            try:
                parser = JsonOutputParser()
                json_res = parser.invoke(llm_res.content)
                return json_res
            except Exception as e:
                raise ValueError(f"Error parsing LLM JSON response: {str(e)}") from e
        elif res_format == "yaml":
            obj_text = get_obj_text("yaml", llm_res.content)
            try:
                yaml_res = yaml.safe_load(obj_text)
                return yaml_res
            except Exception as e:
                raise ValueError(f"Error parsing LLM YAML response: {str(e)}") from e
        else:
            return llm_res.content

    @abstractmethod
    def invoke_model(
        self, input_message, messages, session_id=None, clear_history=False
    ):
        pass
