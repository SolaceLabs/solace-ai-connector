"""LiteLLM chat model component with conversation history"""

import time

from .litellm_chat_model_base import LiteLLMChatModelBase, litellm_chat_info_base
from ..common.chat_history_handler import ChatHistoryHandler
from .....common.log import log

info = litellm_chat_info_base.copy()
info["class_name"] = "LiteLLMChatModelWithHistory"
info["description"] = "LiteLLM model handler component with conversation history"
info["config_parameters"].extend(
    [
        {
            "name": "history_max_turns",
            "required": False,
            "description": "Maximum number of conversation turns to keep in history",
            "default": 10,
        },
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


class LiteLLMChatModelWithHistory(LiteLLMChatModelBase, ChatHistoryHandler):

    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        self.history_max_turns = self.get_config("history_max_turns", 10)
        self.history_max_time = self.get_config("history_max_time", 3600)
        self.history_key = f"{self.flow_name}_{self.name}_history"

        # Set up hourly timer for history cleanup
        self.add_timer(3600000, "history_cleanup", interval_ms=3600000)

    def invoke(self, message, data):
        session_id = data.get("session_id")
        if not session_id:
            raise ValueError("session_id is not provided") from None

        clear_history_but_keep_depth = data.get("clear_history_but_keep_depth")
        try:
            if clear_history_but_keep_depth is not None:
                clear_history_but_keep_depth = max(0, int(clear_history_but_keep_depth))
        except (TypeError, ValueError):
            log.error("Invalid clear_history_but_keep_depth value. Defaulting to 0.")
            clear_history_but_keep_depth = 0
        messages = data.get("messages", [])
        stream = data.get("stream")

        with self.get_lock(self.history_key):
            history = self.kv_store_get(self.history_key) or {}
            if session_id not in history:
                history[session_id] = {"messages": [], "last_accessed": time.time()}

            if clear_history_but_keep_depth is not None:
                self.clear_history_but_keep_depth(
                    session_id, clear_history_but_keep_depth, history
                )

            session_history = history[session_id]["messages"]
            log.debug("Got session history")

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
                message, {"messages": history[session_id]["messages"], "stream": stream}
            )

            # Add the assistant's response to the history
            history[session_id]["messages"].append(
                {
                    "role": "assistant",
                    "content": response["content"],
                }
            )

            self.kv_store_set(self.history_key, history)
            log.debug("Updated history")

        return response
