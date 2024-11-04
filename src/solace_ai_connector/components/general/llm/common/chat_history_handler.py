"""Generic chat history handler."""

import time
from ....component_base import ComponentBase
from .....common.log import log

class ChatHistoryHandler(ComponentBase):
    def __init__(self, info, **kwargs):
        super().__init__(info, **kwargs)
        self.history_max_turns = self.get_config("history_max_turns", 10)
        self.history_max_time = self.get_config("history_max_time", 3600)
        self.history_key = f"{self.flow_name}_{self.name}_history"

        # Set up hourly timer for history cleanup
        self.add_timer(3600000, "history_cleanup", interval_ms=3600000)

    def prune_history(self, session_id, history):
        current_time = time.time()
        if current_time - history[session_id]["last_accessed"] > self.history_max_time:
            history[session_id]["messages"] = []
        elif len(history[session_id]["messages"]) > self.history_max_turns * 2:
            history[session_id]["messages"] = history[session_id]["messages"][
                -self.history_max_turns * 2 :
            ]
        log.debug(f"Pruned history for session {session_id}")
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
            log.info(f"Cleared history for session {session_id}")

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
                    log.info(f"Removed history for session {session_id}")
            self.kv_store_set(self.history_key, history)
