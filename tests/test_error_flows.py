"""This file contains tests for configured flows to handle errors"""

import sys

sys.path.append("src")

# import queue

from solace_ai_connector.test_utils.utils_for_test_files import (  # pylint: disable=wrong-import-position
    create_test_flows,
    # create_and_run_component,
    dispose_connector,
    send_message_to_flow,
    get_message_from_flow,
)
from solace_ai_connector.common.message import (  # pylint: disable=wrong-import-position
    Message,
)


def test_basic_error_flow():
    """Test the basic error flow"""
    # Create a simple configuration
    config_yaml = """
instance_name: test_instance
log:
  log_file_level: DEBUG
  log_file: solace_ai_connector.log
flows:
  # This will fail with the specified error
  - name: fail_flow
    components:
      - component_name: fail
        component_module: fail
        component_config:
          error_message: This is an error message
          exception_type: ValueError

  # This will handle the error
  - name: error_flow
    components:
      - component_name: error_input
        component_module: error_input
      - component_name: pass_through
        component_module: pass_through
        input_selection:
          source_expression: previous:error.text
"""
    connector, flows = create_test_flows(config_yaml)

    input_flow = flows[0]
    output_flow = flows[1]

    # Send a message to the input flow
    send_message_to_flow(input_flow, Message(payload={"text": "Hello, World!"}))

    # Get the output message
    output_message = get_message_from_flow(output_flow)

    try:
        assert output_message.get_data("previous") == "This is an error message"

        error = output_message.get_data("input.payload")["error"]
        assert error["exception"] == "ValueError"
        assert error["text"] == "This is an error message"
    finally:
        dispose_connector(connector)
