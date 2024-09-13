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

import threading
import queue
import time
from typing import Dict, Any


class RequestResponseFlowManager:
    def __init__(self):
        self.flows: Dict[str, Any] = {}

    def add_flow(self, flow_name: str, flow):
        self.flows[flow_name] = flow

    def get_flow(self, flow_name: str):
        return self.flows.get(flow_name)


from typing import Dict, Any, TYPE_CHECKING
from ..common.event import Event, EventType

if TYPE_CHECKING:
    from ..solace_ai_connector import SolaceAiConnector

class RequestResponseController:
    def __init__(
        self, config: Dict[str, Any], connector: 'SolaceAiConnector'
    ):
        self.config = config
        self.connector = connector
        self.flow_name = config["flow_name"]
        self.streaming = config.get("streaming", False)
        self.streaming_last_message_expression = config.get(
            "streaming_last_message_expression"
        )
        self.timeout_ms = config.get("timeout_ms", 30000)
        self.response_queue = queue.Queue()
        self.flow_instance = self.connector.create_flow_instance(self.flow_name)
        self.input_queue = self.flow_instance.get_flow_input_queue()
        self.setup_response_queue()

    def setup_response_queue(self):
        last_component = self.flow_instance.component_groups[-1][-1]
        last_component.set_next_component(self)

    def send_message(self, message: Any):
        if not self.input_queue:
            raise ValueError(f"Input queue for flow {self.flow_name} not found")

        event = Event(EventType.MESSAGE, message)
        self.input_queue.put(event)

    def enqueue(self, event):
        if event.event_type == EventType.MESSAGE:
            self.response_queue.put(event.data)

    def get_response(self):
        try:
            if self.streaming:
                return self._get_streaming_response()
            else:
                return self.response_queue.get(timeout=self.timeout_ms / 1000)
        except queue.Empty:
            raise TimeoutError(
                f"Timeout waiting for response from flow {self.flow_name}"
            )

    def _get_streaming_response(self):
        responses = []
        start_time = time.time()
        while True:
            try:
                response = self.response_queue.get(
                    timeout=(start_time + self.timeout_ms / 1000 - time.time())
                )
                responses.append(response)
                if self.streaming_last_message_expression:
                    if self._is_last_message(response):
                        break
            except queue.Empty:
                if responses:
                    break
                raise TimeoutError(
                    f"Timeout waiting for streaming response from flow {self.flow_name}"
                )
        return responses

    def _is_last_message(self, message):
        # Implement logic to check if this is the last message based on the streaming_last_message_expression
        # This might involve parsing the expression and checking the message content
        pass

    def handle_response(self, response):
        self.response_queue.put(response)
