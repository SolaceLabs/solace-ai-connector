"""OpenAI chat model component with conversation history"""

from copy import deepcopy
from .openai_chat_model_base import OpenAIChatModelBase, openai_info_base
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

info = deepcopy(openai_info_base)
info["class_name"] = "OpenAIChatModelWithHistory"
info["description"] = "OpenAI chat model component with conversation history"
info["config_parameters"].extend([
    {
        "name": "history_max_turns",
        "required": False,
        "description": "Maximum number of conversation turns to keep in history",
        "default": 10,
    },
    {
        "name": "history_class",
        "required": False,
        "description": "The class to use for conversation history",
        "default": "ChatMessageHistory",
    },
])

class OpenAIChatModelWithHistory(OpenAIChatModelBase):
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        self.history = {}
        self.history_max_turns = self.get_config("history_max_turns", 10)
        self.history_class = self.get_config("history_class", "ChatMessageHistory")

    def invoke_model(self, input_message, messages, session_id=None, clear_history=False):
        if clear_history and session_id in self.history:
            del self.history[session_id]

        template = ChatPromptTemplate.from_messages([
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}"),
        ])

        chain = RunnableWithMessageHistory(
            template | self.component,
            lambda session_id: self.get_history(session_id),
            input_messages_key="input",
            history_messages_key="history",
        )

        result = chain.invoke(
            {"input": messages[-1].content},
            config={"configurable": {"session_id": session_id}},
        )

        self.prune_history(session_id)

        return result

    def get_history(self, session_id):
        if session_id not in self.history:
            self.history[session_id] = self.create_history()
        return self.history[session_id]

    def create_history(self):
        from langchain_core.chat_history import ChatMessageHistory
        return ChatMessageHistory()

    def prune_history(self, session_id):
        if session_id in self.history:
            history = self.history[session_id]
            if len(history.messages) > self.history_max_turns * 2:
                history.messages = history.messages[-self.history_max_turns * 2:]
