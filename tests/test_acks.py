"""This file tests acks in a flow"""
import sys
import queue

sys.path.append("src")

from utils_for_test_files import (  # pylint: disable=wrong-import-position
    create_connector,
    create_and_run_component,
    # dispose_connector,
)
from solace_ai_event_connector.common.message import (  # pylint: disable=wrong-import-position
    Message,
)


def test_basic_ack():
    """Test the basic ack"""
    # Create a simple configuration
    config_yaml = """
instance_name: test_instance
log:
  log_file_level: DEBUG
  log_file: solace_ai_event_connector.log
flows:
  - name: test_flow
    components:
      - component_name: need_ack_input
        component_module: need_ack_input
        component_config:
          ack_message: This is an ack message
      - component_name: give_ack_output
        component_module: give_ack_output
"""
    # Setup the error queue
    error_queue = queue.Queue()

    message = Message(payload={"text": "Hello, World!"})
    create_and_run_component(
        config_yaml, message, error_queue=error_queue, no_output=True
    )

    error_message = error_queue.get(timeout=1)
    payload = error_message.get_data("input.payload")
    assert payload["location"] == {
        "instance": "test_instance",
        "flow": "test_flow",
        "component": "give_ack_output",
        "component_index": 0,
    }
    assert payload["error"] == {
        "text": "This is an ack message",
        "exception": "Exception",
    }
    assert payload["message"]["payload"] == {"text": "Hello, World!"}
