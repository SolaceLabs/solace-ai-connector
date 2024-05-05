"""A chat model based on LangChain that includes keeping per-session history of the conversation."""

import threading

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# from langchain.memory import ConversationTokenBufferMemory
from langchain.schema.messages import (
    HumanMessage,
    SystemMessage,
)

from solace_ai_event_connector.flow_components.general.langchain.langchain_chat_model_base import (
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

    def invoke_model(self, messages, session_id=None, clear_history=False):

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

        return runnable.invoke(
            {"input": human_message},
            config={
                "configurable": {"session_id": session_id},
            },
        )

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
