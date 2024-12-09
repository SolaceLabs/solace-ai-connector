"""Input component to receive processing errors from the Solace AI Event Connector. 
Using this component allows the user to decide how to handle errors from other flows. 
For example, the user could send the errors to a log or send them to a broker."""

import time

from ...common.log import log
from ..component_base import (
    ComponentBase,
)

# from solace_ai_connector.common.message import Message

info = {
    "class_name": "ErrorInput",
    "description": (
        "Receive processing errors from the Solace AI Event Connector. Note that "
        "the input_selection configuration is ignored. "
        "This component should be used to create a flow that handles errors from other flows. "
    ),
    "config_parameters": [
        {
            "name": "max_rate",
            "required": False,
            "description": (
                "Maximum rate of errors to process per second. Any errors "
                "above this rate will be dropped. If not set, all errors will be processed."
            ),
            "default": None,
        },
        {
            "name": "max_queue_depth",
            "required": False,
            "description": (
                "Maximum number of messages that can be queued in the input queue."
                "If the queue is full, the new message is dropped."
            ),
            "default": 1000,
        },
    ],
    "output_schema": {
        "type": "object",
        "properties": {
            "error": {
                "type": "object",
                "description": "Information about the error",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The error message",
                    },
                    "exception": {
                        "type": "string",
                        "description": "The exception message",
                    },
                },
                "required": ["message", "exception"],
            },
            "message": {
                "type": "object",
                "description": "The message that caused the error",
                "properties": {
                    "payload": {
                        "type": "string",
                        "description": "The payload of the message",
                    },
                    "topic": {
                        "type": "string",
                        "description": "The topic of the message",
                    },
                    "user_properties": {
                        "type": "object",
                        "description": "The user properties of the message",
                    },
                    "user_data": {
                        "type": "object",
                        "description": "The user data of the message that was created during the flow",
                    },
                    "previous": {
                        "type": "object",
                        "description": "The output from the previous stage that was processed before the error",
                    },
                },
                "required": [],
            },
            "location": {
                "type": "object",
                "description": "The location where the error occurred",
                "properties": {
                    "instance": {
                        "type": "integer",
                        "description": "The instance number of the component that generated the error",
                    },
                    "flow": {
                        "type": "string",
                        "description": "The flow name of the component that generated the error",
                    },
                    "component": {
                        "type": "string",
                        "description": "The component name that generated the error",
                    },
                },
                "required": ["flow", "component"],
            },
        },
        "required": ["error", "message", "location"],
    },
}


class ErrorInput(ComponentBase):

    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        self.max_rate = self.get_config("max_rate")
        self.max_queue_depth = self.get_config("max_queue_depth")
        self.error_count_in_last_second = 0
        self.error_count_start_time = time.time()

        # Change our input queue to be the error queue
        self.input_queue = self.error_queue
        # Set error_queue to None so that we don't enqueue to ourselves
        self.error_queue = None

    def invoke(self, message, data):
        if (
            self.discard_message_due_to_input_rate()
            or self.discard_message_due_to_full_queue()
        ):
            return None
        return data

    def discard_message_due_to_input_rate(self):
        if self.max_rate is None:
            return False
        curr_time = time.time()

        if curr_time - self.error_count_start_time > 1:
            self.error_count_start_time = curr_time
            self.error_count_in_last_second = 1
        else:
            self.error_count_in_last_second += 1
            if self.error_count_in_last_second > self.max_rate:
                log.warning(
                    "Discarding error message due to input rate limit. "
                    "Error rate exceeded max rate of %d.",
                    self.max_rate,
                )
                return True
        return False

    def discard_message_due_to_full_queue(self):
        if self.input_queue.qsize() < self.max_queue_depth:
            return False

        log.warning(
            "Discarding error message due to queue size. "
            "Error queue reached max queue depth of %d.",
            self.max_queue_depth,
        )
        return True

    def get_input_data(self, message):
        return message.get_data("input.payload")
