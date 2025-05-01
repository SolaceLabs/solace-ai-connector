# This is the base class of a wrapper around all the LangChain chat models
# The configuration will control dynamic loading of the chat models

import yaml
from abc import abstractmethod
from langchain_core.output_parsers import JsonOutputParser

from .....common.message import Message
from .....common.utils import get_obj_text
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
            "name": "llm_mode",
            "required": False,
            "description": "The mode for streaming results: 'none' or 'stream'. 'stream' will just stream the results to the named flow. 'none' will wait for the full response.",
        },
        {
            "name": "stream_to_flow",
            "required": False,
            "description": "Name the flow to stream the output to - this must be configured for llm_mode='stream'.",
            "default": "",
        },
        {
            "name": "stream_batch_size",
            "required": False,
            "description": "The minimum number of words in a single streaming result. Default: 15.",
            "default": 15,
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

    def __init__(self, info, **kwargs):
        super().__init__(info, **kwargs)
        self.llm_mode = self.get_config("llm_mode", "none")
        self.stream_to_flow = self.get_config("stream_to_flow", "")
        self.stream_batch_size = self.get_config("stream_batch_size", 15)

    def invoke(self, message, data):
        messages = []

        for item in data.get("messages"):
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
                ) from None

        session_id = data.get("session_id", None)
        clear_history = data.get("clear_history", False)
        stream = data.get("stream", self.llm_mode == "stream")

        llm_res = self.invoke_model(
            message,
            messages,
            session_id=session_id,
            clear_history=clear_history,
            stream=stream,
        )

        res_format = self.get_config("llm_response_format", "text")
        if res_format == "json":
            try:
                parser = JsonOutputParser()
                json_res = parser.invoke(llm_res.content)
                return json_res
            except Exception:
                raise ValueError("Error parsing LLM JSON response") from None
        elif res_format == "yaml":
            obj_text = get_obj_text("yaml", llm_res.content)
            try:
                yaml_res = yaml.safe_load(obj_text)
                return yaml_res
            except Exception:
                raise ValueError("Error parsing LLM YAML response") from None
        else:
            return llm_res.content

    @abstractmethod
    def invoke_model(
        self,
        input_message,
        messages,
        session_id=None,
        clear_history=False,
        stream=False,
    ):
        pass

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
            },
            user_properties=input_message.get_user_properties(),
        )
        self.send_to_flow(self.stream_to_flow, message)
