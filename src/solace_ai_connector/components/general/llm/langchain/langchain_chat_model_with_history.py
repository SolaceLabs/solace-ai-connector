"""A chat model based on LangChain that includes keeping per-session history of the conversation."""

import threading
import time
from collections import namedtuple
from copy import deepcopy
from uuid import uuid4

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# from langchain.memory import ConversationTokenBufferMemory
from langchain.schema.messages import (
    HumanMessage,
    SystemMessage,
)

from .langchain_chat_model_base import (
    LangChainChatModelBase,
    info_base,
)


info = deepcopy(info_base)
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
            "name": "history_max_message_size",
            "required": False,
            "description": "The maximum amount of characters to keep in a single message in the history. ",
            "default": 1000,
        },
        {
            "name": "history_max_tokens",
            "required": False,
            "description": "The maximum number of tokens to keep in the history. "
            "If not set, the history will be limited to 8000 tokens.",
            "default": 8000,
        },
        {
            "name": "history_max_time",
            "required": False,
            "description": "The maximum time (in seconds) to keep messages in the history. "
            "If not set, messages will not expire based on time.",
            "default": None,
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
            "name": "set_response_uuid_in_user_properties",
            "required": False,
            "description": "Whether to set the response_uuid in the user_properties of the input_message. This will allow other components to correlate streaming chunks with the full response.",
            "default": False,
            "type": "boolean",
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
        super().__init__(info, **kwargs)
        self.history_max_turns = self.get_config("history_max_turns", 20)
        self.history_max_message_size = self.get_config(
            "history_max_message_size", 1000
        )
        self.history_max_tokens = self.get_config("history_max_tokens", 8000)
        self.history_max_time = self.get_config("history_max_time", None)
        self.set_response_uuid_in_user_properties = self.get_config(
            "set_response_uuid_in_user_properties", False
        )

    def invoke_model(
        self,
        input_message,
        messages,
        session_id=None,
        clear_history=False,
        stream=False,
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

        if not stream:
            return runnable.invoke(
                {"input": human_message},
                config={
                    "configurable": {"session_id": session_id},
                },
            )

        aggregate_result = ""
        current_batch = ""
        response_uuid = str(uuid4())
        first_chunk = True
        for chunk in runnable.stream(
            {"input": human_message},
            config={
                "configurable": {"session_id": session_id},
            },
        ):
            aggregate_result += chunk.content
            current_batch += chunk.content
            if len(current_batch.split()) >= self.stream_batch_size:
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

        self.prune_large_message_from_history(session_id)

        return result

    def create_history(self):

        history_class = self.load_component(
            self.get_config(
                "history_module", "langchain_community.chat_message_histories"
            ),
            self.get_config("history_class", "ChatMessageHistory"),
        )
        config = self.get_config("history_config", {})
        history = self.create_component(config, history_class)
        return history

    def get_history(self, session_id: str) -> BaseChatMessageHistory:
        with self._lock:
            if session_id not in self._histories:
                self._histories[session_id] = self.create_history()

            # Get all the messages from the history
            messages = self._histories[session_id].messages

            # Prune messages based on max turns
            if len(messages) > self.history_max_turns:
                messages = messages[-self.history_max_turns :]

            # Prune messages based on max time
            if self.history_max_time is not None:
                current_time = time.time()
                messages = [
                    msg
                    for msg in messages
                    if (current_time - msg.additional_kwargs.get("timestamp", 0))
                    <= self.history_max_time
                ]

            # Update the history with pruned messages
            self._histories[session_id].messages = messages

            return self._histories[session_id]

    def prune_large_message_from_history(self, session_id: str):
        with self._lock:
            # Loop over the last 2 messages in the history and truncate if needed
            if (
                session_id in self._histories
                and len(self._histories[session_id].messages) > 1
            ):
                last_two_messages = self._histories[session_id].messages[-2:]
                for message in last_two_messages:
                    if len(message.content) > self.history_max_message_size:
                        message.content = (
                            message.content[: self.history_max_message_size]
                            + " ...truncated..."
                        )

    def clear_history(self, session_id: str):
        with self._lock:
            if session_id in self._histories:
                del self._histories[session_id]
