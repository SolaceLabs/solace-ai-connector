"""A flow component that aggregates messages"""

import time
import math

from ...common.log import log
from ..component_base import ComponentBase
from ...common.message import Message

info = {
    "class_name": "Aggregate",
    "description": "Take multiple messages and aggregate them into one. "
    "The output of this component is a list of the exact structure "
    "of the input data.",
    "short_description": "Aggregate messages into one message.",
    "config_parameters": [
        {
            "name": "max_items",
            "required": False,
            "default": 10,
            "type": "integer",
            "description": "Number of input messages to aggregate before sending an output message",
        },
        {
            "name": "max_time_ms",
            "required": False,
            "description": "Number of milliseconds to wait before sending an output message",
            "default": 1000,
            "type": "integer",
        },
    ],
    "input_schema": {
        "type": "object",
        "description": "The input message to be aggregated",
        "properties": {},
    },
    "output_schema": {
        "type": "array",
        "description": "The aggregated messages",
        "items": {
            "type": "object",
        },
    },
}


class Aggregate(ComponentBase):
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        self.current_aggregation = None
        self.aggregate_dest = self.get_config("aggregate_dest")
        self.max_time_ms = self.get_config("max_time_ms")
        self.max_items = self.get_config("max_items")

    def invoke(self, message, data):
        # The passed in data is the date specified by component_input
        # from the config file
        if self.current_aggregation is None:
            self.current_aggregation = self.start_new_aggregation()

        is_expired, remaining_time = self.update_queue_timer()

        self.current_aggregation["list"].append(data)
        message.combine_with_message(self.current_aggregation["message"])

        # If the aggregation is full or timed out, send it
        if is_expired or len(self.current_aggregation["list"]) >= self.max_items:
            self.set_queue_timeout(None)
            log.debug("Aggregation done - sending: %s", self.current_aggregation)
            self.send_aggregation()
            return None

        # Aggregation is not full, so set the timer to the remaining time
        self.set_queue_timeout(remaining_time)

        # Otherwise, return None to indicate that no message should be sent
        return None

    def update_queue_timer(self):
        # Get the epoch time in milliseconds
        epoch_time_ms = math.floor(time.time() * 1000)

        # How much time is left on the timer
        remaining_time = (
            self.current_aggregation["next_aggregation_time"] - epoch_time_ms
        )

        if remaining_time <= 0:
            return True, self.max_time_ms

        return False, remaining_time

    def handle_queue_timeout(self):
        # If we have an aggregation, send it
        if self.current_aggregation is not None:
            self.send_aggregation()
        else:
            # Otherwise, clear the timer
            self.set_queue_timeout(None)

    def send_aggregation(self):
        # Send the aggregation
        data, message = self.complete_aggregation()
        self.process_post_invoke(data, message)

    def start_new_aggregation(self):
        # Get the epoch time in milliseconds
        epoch_time_ms = math.floor(time.time() * 1000)
        next_time_for_timeout = self.max_time_ms + epoch_time_ms
        return {
            "list": [],
            "next_aggregation_time": next_time_for_timeout,
            "message": Message(),
        }

    def complete_aggregation(self):
        log.debug("Completing aggregation")
        aggregation = self.current_aggregation
        self.current_aggregation = None
        return aggregation["list"], aggregation["message"]

    # def get_default_queue_timeout(self):
    #     return self.get_config("max_time_ms")
