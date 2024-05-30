"""A chat model based on LangChain that includes keeping per-session history of the conversation."""

import threading
from collections import namedtuple

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# from langchain.memory import ConversationTokenBufferMemory
from langchain.schema.messages import (
    HumanMessage,
    SystemMessage,
)

from ....common.message import Message
from .langchain_chat_model_base import (
    LangChainChatModelBase,
    info_base,
)


info = info_base
info["class_name"] = "LangChainChatModelWithHistory"
info["description"] = (
    "A chat model based on LangChain that includes keeping per-session history of "
    "the conversation. Note that this component will only take the first system "
    "message and the first human message in the messages array."
)
info["config_parameters"].extend(
    [
        {
            "name": "history_max_turns",
            "required": False,
            "description": "The maximum number of turns to keep in the history. "
            "If not set, the history will be limited to 20 turns.",
            "default": 20,
        },
        {
            "name": "history_max_tokens",
            "required": False,
            "description": "The maximum number of tokens to keep in the history. "
            "If not set, the history will be limited to 8000 tokens.",
            "default": 8000,
        },
        {
            "name": "history_module",
            "required": False,
            "description": "The module that contains the history class. "
            "Default: 'langchain_community.chat_message_histories'",
            "default": "langchain_community.chat_message_histories",
        },
        {
            "name": "history_class",
            "required": False,
            "description": "The class to use for the history. Default: 'ChatMessageHistory'",
            "default": "ChatMessageHistory",
        },
        {
            "name": "history_config",
            "required": False,
            "description": "The configuration for the history class.",
            "type": "object",
        },
        {
            "name": "stream_to_flow",
            "required": False,
            "description": "Name the flow to stream the output to - this must be configured for llm_mode='stream'.",
            "default": "",
        },
        {
            "name": "llm_mode",
            "required": False,
            "description": "The mode for streaming results: 'sync' or 'stream'. 'stream' will just stream the results to the named flow. 'none' will wait for the full response.",
        },
        {
            "name": "stream_batch_size",
            "required": False,
            "description": "The minimum number of words in a single streaming result. Default: 15.",
            "default": 15,
        },
    ]
)
info["input_schema"]["properties"]["session_id"] = {
    "type": "string",
    "description": "The session ID for the conversation.",
}
info["input_schema"]["required"].append("session_id")
info["input_schema"]["properties"]["clear_history"] = {
    "type": "boolean",
    "description": "Whether to clear the history for the session.",
    "default": False,
}


class LangChainChatModelWithHistory(LangChainChatModelBase):
    _histories: dict = {}
    _lock = threading.Lock()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.history_max_turns = self.get_config("history_max_turns", 20)
        self.history_max_tokens = self.get_config("history_max_tokens", 8000)
        self.stream_to_flow = self.get_config("stream_to_flow", "")
        self.llm_mode = self.get_config("llm_mode", "none")
        self.stream_batch_size = self.get_config("stream_batch_size", 15)

    def invoke_model(
        self, input_message, messages, session_id=None, clear_history=False
    ):

        if clear_history:
            self.clear_history(session_id)

        # Find the first SystemMessage and HumanMessage
        system_prompt = "You are a helpful assistant."
        for message in messages:
            if isinstance(message, SystemMessage):
                system_prompt = message.content
                break

        human_message = ""
        for message in messages:
            if isinstance(message, HumanMessage):
                human_message = message.content
                break

        # Create the prompt template
        template = ChatPromptTemplate.from_messages(
            [
                SystemMessage(system_prompt),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{input}"),
            ]
        )

        runnable = RunnableWithMessageHistory(
            template | self.component,
            self.get_history,
            input_messages_key="input",
            history_messages_key="chat_history",
        )

        if self.llm_mode == "none":
            return runnable.invoke(
                {"input": human_message},
                config={
                    "configurable": {"session_id": session_id},
                },
            )

        aggregate_result = ""
        current_batch = ""
        for chunk in runnable.stream(
            {"input": human_message},
            config={
                "configurable": {"session_id": session_id},
            },
        ):
            # print(f"Streaming chunk: {chunk.content}")
            aggregate_result += chunk.content
            current_batch += chunk.content
            if len(current_batch.split()) >= self.stream_batch_size:
                if self.stream_to_flow:
                    self.send_streaming_message(
                        input_message, current_batch, aggregate_result
                    )
                current_batch = ""

        if current_batch:
            if self.stream_to_flow:
                self.send_streaming_message(
                    input_message, current_batch, aggregate_result
                )

        result = namedtuple("Result", ["content"])(aggregate_result)

        return result

    def send_streaming_message(self, input_message, chunk, aggregate_result):
        message = Message(
            payload={"chunk": chunk, "aggregate_result": aggregate_result},
            user_properties=input_message.get_user_properties(),
        )
        self.send_to_flow(self.stream_to_flow, message)

    def create_history(self):

        history_class = self.load_component(
            self.get_config(
                "history_module", "langchain_community.chat_message_histories"
            ),
            self.get_config("history_class", "ChatMessageHistory"),
        )
        config = self.get_config("history_config", {})
        history = self.create_component(config, history_class)
        # memory = ConversationTokenBufferMemory(
        #     chat_memory=history, llm=self.component, max_token_limit=history_max_tokens
        # )
        return history

    def get_history(self, session_id: str) -> BaseChatMessageHistory:
        with self._lock:
            # TBD - we could do some history pruning here if we can't beat langchain into submission
            #       for now just implement the turns limit - later can look at tokens
            if session_id not in self._histories:
                self._histories[session_id] = self.create_history()
            # Get all the messages from the history
            messages = self._histories[session_id].messages
            if len(messages) > self.history_max_turns:
                # Set the history to the last max_turns messages
                self._histories[session_id].messages = messages[
                    -self.history_max_turns :
                ]
            return self._histories[session_id]

    def clear_history(self, session_id: str):
        with self._lock:
            if session_id in self._histories:
                del self._histories[session_id]
