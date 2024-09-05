"""OpenAI chat model component with conversation history"""

import time

import time
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
            "description": "Maximum time to keep conversation history (in seconds)",
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
        self.history_max_turns = self.get_config("history_max_turns", 10)
        self.history_max_time = self.get_config("history_max_time", 3600)
        self.history_key = f"{self.flow_name}_{self.name}_history"

        # Set up hourly timer for history cleanup
        self.add_timer(3600000, "history_cleanup", interval_ms=3600000)

    def invoke(self, message, data):
        session_id = data.get("session_id")
        clear_history_but_keep_depth = data.get("clear_history_but_keep_depth")
        messages = data.get("messages", [])

        with self.get_lock(self.history_key):
            history = self.kv_store_get(self.history_key) or {}

            if session_id not in history:
                history[session_id] = {"messages": [], "last_accessed": time.time()}

            if clear_history_but_keep_depth is not None:
                self.clear_history_but_keep_depth(
                    session_id, clear_history_but_keep_depth, history
                )

            session_history = history[session_id]["messages"]

            # If the passed in messages have a system message and the history's
            # first message is a system message, then replace the history's first
            # message with the passed in messages' system message
            if (
                len(messages)
                and messages[0]["role"] == "system"
                and len(session_history)
                and session_history[0]["role"] == "system"
            ):
                session_history[0] = messages[0]
                session_history.extend(messages[1:])
            else:
                session_history.extend(messages)

            history[session_id]["last_accessed"] = time.time()

            self.prune_history(session_id, history)

            response = super().invoke(
                message, {"messages": history[session_id]["messages"]}
            )

            # Add the assistant's response to the history
            history[session_id]["messages"].append(
                {
                    "role": "assistant",
                    "content": response["content"],
                }
            )

            self.kv_store_set(self.history_key, history)

        return response

    def prune_history(self, session_id, history):
        current_time = time.time()
        if current_time - history[session_id]["last_accessed"] > self.history_max_time:
            history[session_id]["messages"] = []
        elif len(history[session_id]["messages"]) > self.history_max_turns * 2:
            history[session_id]["messages"] = history[session_id]["messages"][
                -self.history_max_turns * 2 :
            ]
        self.make_history_start_with_user_message(session_id, history)

    def clear_history_but_keep_depth(self, session_id: str, depth: int, history):
        if session_id in history:
            messages = history[session_id]["messages"]
            # If the depth is 0, then clear all history
            if depth == 0:
                history[session_id]["messages"] = []
                history[session_id]["last_accessed"] = time.time()
                return

            # Check if the history is already shorter than the depth
            if len(messages) <= depth:
                # Do nothing, since the history is already shorter than the depth
                return

            # If the message at depth is not a user message, then
            # increment the depth until a user message is found
            while depth < len(messages) and messages[-depth]["role"] != "user":
                depth += 1
            history[session_id]["messages"] = messages[-depth:]
            history[session_id]["last_accessed"] = time.time()

            # In the unlikely case that the history starts with a non-user message,
            # remove it
            self.make_history_start_with_user_message(session_id, history)

    def make_history_start_with_user_message(self, session_id, history):
        if session_id in history:
            messages = history[session_id]["messages"]
            if messages:
                if messages[0]["role"] == "system":
                    # Start from the second message if the first is "system"
                    start_index = 1
                else:
                    # Start from the first message otherwise
                    start_index = 0

                while (
                    start_index < len(messages)
                    and messages[start_index]["role"] != "user"
                ):
                    messages.pop(start_index)

    def handle_timer_event(self, timer_data):
        if timer_data["timer_id"] == "history_cleanup":
            self.history_age_out()

    def history_age_out(self):
        with self.get_lock(self.history_key):
            history = self.kv_store_get(self.history_key) or {}
            current_time = time.time()
            for session_id in list(history.keys()):
                if (
                    current_time - history[session_id]["last_accessed"]
                    > self.history_max_time
                ):
                    del history[session_id]
            self.kv_store_set(self.history_key, history)
