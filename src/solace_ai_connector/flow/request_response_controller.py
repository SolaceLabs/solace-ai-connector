"""
This file will handle sending a message to a named flow and then 
receiving the output message from that flow. It will also support the result
message being a streamed message that comes in multiple parts. 

Each component can optionally create multiple of these using the configuration:

```yaml
- name: example_flow
  components:
    - component_name: example_component
      component_module: custom_component
      request_response_controllers:
        - name: example_controller
          flow_name: llm_flow
          streaming: true
          streaming_last_message_expression: input.payload:streaming.last_message
          timeout_ms: 300000
```

"""

import queue
import time
from typing import Dict, Any

from ..common.message import Message
from ..common.event import Event, EventType


# This is a very basic component which will be stitched onto the final component in the flow
class RequestResponseControllerOuputComponent:
    def __init__(self, controller):
        self.controller = controller

    def enqueue(self, event):
        self.controller.enqueue_response(event)


# This is the main class that will be used to send messages to a flow and receive the response
class RequestResponseFlowController:
    def __init__(self, config: Dict[str, Any], connector: "SolaceAiConnector"):
        self.config = config
        self.connector = connector
        self.flow_name = config.get("flow_name")
        self.streaming = config.get("streaming", False)
        self.streaming_last_message_expression = config.get(
            "streaming_last_message_expression"
        )
        self.timeout_s = config.get("timeout_ms", 30000) / 1000
        self.input_queue = None
        self.response_queue = None
        self.enqueue_time = None
        self.request_outstanding = False

        flow = connector.get_flow(self.flow_name)

        if not flow:
            raise ValueError(f"Flow {self.flow_name} not found")

        self.setup_queues(flow)

    def setup_queues(self, flow):
        # Input queue to send the message to the flow
        self.input_queue = flow.get_input_queue()

        # Response queue to receive the response from the flow
        self.response_queue = queue.Queue()
        rrcComponent = RequestResponseControllerOuputComponent(self)
        flow.set_next_component(rrcComponent)

    def send_message(self, message: Message, data: Any):
        # Make a new message, but copy the data from the original message
        payload = message.get_payload()
        topic = message.get_topic()
        user_properties = message.get_user_properties()
        new_message = Message(
            payload=payload, topic=topic, user_properties=user_properties
        )
        new_message.set_previous(data)

        if not self.input_queue:
            raise ValueError(f"Input queue for flow {self.flow_name} not found")

        event = Event(EventType.MESSAGE, new_message)
        self.enqueue_time = time.time()
        self.request_outstanding = True
        self.input_queue.put(event)
        return self.response_iterator

    def response_iterator(self):
        while True:
            now = time.time()
            elapsed_time = now - self.enqueue_time
            remaining_timeout = self.timeout_s - elapsed_time
            if self.streaming:
                # If we are in streaming mode, we will return individual messages
                # until we receive the last message. Use the expression to determine
                # if this is the last message
                while True:
                    try:
                        event = self.response_queue.get(timeout=remaining_timeout)
                        if event.event_type == EventType.MESSAGE:
                            message = event.data
                            yield message, message.get_previous()
                            if self.streaming_last_message_expression:
                                last_message = message.get_data(
                                    self.streaming_last_message_expression
                                )
                                if last_message:
                                    return
                    except queue.Empty:
                        if (time.time() - self.enqueue_time) > self.timeout_s:
                            raise TimeoutError("Timeout waiting for response")

            else:
                # If we are not in streaming mode, we will return a single message
                # and then stop the iterator
                try:
                    event = self.response_queue.get(timeout=remaining_timeout)
                    if event.event_type == EventType.MESSAGE:
                        message = event.data
                        yield message, message.get_previous()
                        return
                except queue.Empty:
                    if (time.time() - self.enqueue_time) > self.timeout_s:
                        raise TimeoutError("Timeout waiting for response")

    def enqueue_response(self, event):
        self.response_queue.put(event)
