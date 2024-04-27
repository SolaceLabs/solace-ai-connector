import time
from copy import deepcopy


from solace_ai_event_connector.flow_components.component_base import ComponentBase
from solace_ai_event_connector.common.message import Message

from solace_ai_event_connector.common.log import log


info = {
    "class_name": "TimerInput",
    "description": "An input that will generate a message at a specified interval.",
    "config_parameters": [
        {
            "name": "interval_ms",
            "type": "string",
            "description": "The interval in milliseconds at which to generate a message.",
        },
        {
            "name": "skip_messages_if_behind",
            "type": "boolean",
            "description": "If false, when the component is blocked for some time, "
            "it will catch up by generating multiple messages in quick succession. If true, "
            "then the component will always wait at least the interval time before "
            "generating the next message. Note that due to some messages in the pipeline, there "
            "will always be a couple of quick messages generated.",
        },
    ],
    "output_schema": "any",
}


class TimerInput(ComponentBase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.interval_ms = self.get_config("interval_ms")
        self.skip_messages_if_behind = self.get_config("skip_messages_if_behind")
        self.last_message_time = None

    def get_next_message(self):
        # Get the delta time since the last message
        current_time = self.get_current_time()
        if not self.last_message_time:
            self.last_message_time = current_time
        delta_time = (current_time - self.last_message_time) * 1000
        log.debug(
            f"Get message. Current time: {current_time}, last message time: {self.last_message_time}, delta time: {delta_time}"
        )
        if delta_time >= self.interval_ms:
            if self.skip_messages_if_behind:
                self.last_message_time = current_time
            else:
                self.last_message_time += self.interval_ms / 1000
            return Message(payload={})
        else:
            # Sleep for the remaining time
            sleep_time = (self.interval_ms - delta_time) / 1000
            log.debug(f"Sleeping for {sleep_time} s")
            self.last_message_time += sleep_time
            time.sleep(sleep_time)

        return Message(payload={})

    def get_current_time(self):
        return time.time()

    def invoke(self, message, data):
        return deepcopy(message.get_payload())
