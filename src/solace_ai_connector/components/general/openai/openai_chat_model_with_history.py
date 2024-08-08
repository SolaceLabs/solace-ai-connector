"""OpenAI chat model component with conversation history"""

from .openai_chat_model_base import OpenAIChatModelBase, openai_info_base

info = openai_info_base.copy()
info["class_name"] = "OpenAIChatModelWithHistory"
info["description"] = "OpenAI chat model component with conversation history"
info["config_parameters"].extend(
    [
        {
            "name": "history_max_turns",
            "required": False,
            "description": "Maximum number of conversation turns to keep in history",
            "default": 10,
        },
        # Add a config for history max time
        {
            "name": "history_max_time",
            "required": False,
            "description": "Maximum time to keep conversation history",
            "default": 3600,
        },
    ]
)

info["input_schema"]["properties"]["clear_history_but_keep_depth"] = {
    "type": "integer",
    "minimum": 0,
    "description": "Clear history but keep the last N messages. If 0, clear all history. If not set, do not clear history.",
}


class OpenAIChatModelWithHistory(OpenAIChatModelBase):
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        self.history = {}
        self.history_max_turns = self.get_config("history_max_turns", 10)

    def invoke(self, message, data):
        session_id = data.get("session_id")
        clear_history_but_keep_depth = data.get("clear_history_but_keep_depth")
        messages = data.get("messages", [])

        if clear_history_but_keep_depth is not None:
            self.clear_history_but_keep_depth(session_id, clear_history_but_keep_depth)
        elif session_id not in self.history:
            self.history[session_id] = []

        self.history[session_id].extend(messages)
        self.prune_history(session_id)

        response = super().invoke(message, {"messages": self.history[session_id]})

        # Add the assistant's response to the history
        self.history[session_id].append(
            {"role": "assistant", "content": response["content"]}
        )
        self.prune_history(session_id)

        return response

    def prune_history(self, session_id):
        if len(self.history[session_id]) > self.history_max_turns * 2:
            self.history[session_id] = self.history[session_id][
                -self.history_max_turns * 2 :
            ]
