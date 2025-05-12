"""This file tests nacks in a flow"""

import sys
import os

sys.path.append("src")
import queue

from solace_ai_connector.test_utils.utils_for_test_files import (  # pylint: disable=wrong-import-position
    dispose_connector,
    create_test_flows,
    send_message_to_flow,
)
from solace_ai_connector.common.message import (  # pylint: disable=wrong-import-position
    Message,
)
from solace_ai_connector.common import Message_NACK_Outcome  # pylint: disable=wrong-import-position


def test_basic_nack_rejected():
    """Test the basic nack with REJECTED outcome"""
    # Create a simple configuration
    config_yaml = """
instance_name: test_instance
log:
  log_file_level: DEBUG
  log_file: solace_ai_connector.log
flows:
  - name: test_flow
    components:
      - component_name: need_nack_input
        component_module: need_nack_input
        component_config:
          nack_message: This is a nack message
      - component_name: give_nack_output
        component_module: give_nack_output
        component_config:
          nack_outcome: REJECTED
"""
    # Setup the error queue
    error_queue = queue.Queue()

    connector, flows = create_test_flows(config_yaml, error_queue=error_queue)
    flow = flows[0]

    message = Message(payload={"text": "Hello, World!"})
    send_message_to_flow(flow, message)

    try:
        error_event = error_queue.get(timeout=5)
        error_message = error_event.data
        payload = error_message.get_data("input.payload")
        assert payload["location"] == {
            "instance": "test_instance",
            "flow": "test_flow",
            "component": "give_nack_output",
            "component_index": 0,
        }
        print(payload["error"]["text"])
        assert (
            payload["error"]["text"]
            == "This is a nack message with outcome Outcome.REJECTED"
        )
        assert payload["error"]["exception"] == "Exception"
        assert payload["message"]["payload"] == {"text": "Hello, World!"}
    finally:
        dispose_connector(connector)


def test_basic_nack_failed():
    """Test the basic nack with FAILED outcome"""
    # Create a simple configuration
    config_yaml = """
instance_name: test_instance
log:
  log_file_level: DEBUG
  log_file: solace_ai_connector.log
flows:
  - name: test_flow
    components:
      - component_name: need_nack_input
        component_module: need_nack_input
        component_config:
          nack_message: This is a nack message
      - component_name: give_nack_output
        component_module: give_nack_output
        component_config:
          nack_outcome: FAILED
"""
    # Setup the error queue
    error_queue = queue.Queue()

    connector, flows = create_test_flows(config_yaml, error_queue=error_queue)
    flow = flows[0]

    message = Message(payload={"text": "Hello, World!"})
    send_message_to_flow(flow, message)

    try:
        error_event = error_queue.get(timeout=5)
        error_message = error_event.data
        payload = error_message.get_data("input.payload")
        assert payload["location"] == {
            "instance": "test_instance",
            "flow": "test_flow",
            "component": "give_nack_output",
            "component_index": 0,
        }
        assert (
            payload["error"]["text"]
            == "This is a nack message with outcome Outcome.FAILED"
        )
        assert payload["error"]["exception"] == "Exception"
        assert payload["message"]["payload"] == {"text": "Hello, World!"}
    finally:
        dispose_connector(connector)
