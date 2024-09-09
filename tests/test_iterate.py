"""Some tests to verify the iterate component works as expected"""

import sys

sys.path.append("src")

# import pytest

from solace_ai_connector.test_utils.utils_for_test_files import (
    create_test_flows,
    # create_connector,
    dispose_connector,
    # send_and_receive_message_on_flow,
    send_message_to_flow,
    get_message_from_flow,
)
from solace_ai_connector.common.message import Message

# from solace_ai_connector.common.log import log


def test_small_list():
    """Test the iterate component with a small list"""
    config_yaml = """
log:
  log_file_level: DEBUG
  log_file: solace_ai_connector.log
flows:
  - name: test_flow
    components:
      - component_name: iterate
        component_module: iterate
        input_selection:
          source_expression: input.payload:my_list
"""
    connector, flows = create_test_flows(config_yaml)
    flow = flows[0]

    # Send a list of 3 items
    message = Message(payload={"my_list": [1, 2, 3]})
    send_message_to_flow(flow, message)

    # Get the output messages
    for i in range(3):
        output_message = get_message_from_flow(flow)
        assert output_message.get_data("previous") == i + 1

    # Clean up
    dispose_connector(connector)


def test_large_list():
    """Test the iterate component with a large list"""
    config_yaml = """
log:
  log_file_level: DEBUG
  log_file: solace_ai_connector.log
flows:
  - name: test_flow
    components:
      - component_name: iterate
        component_module: iterate
        input_selection:
          source_expression: input.payload:my_list
"""
    connector, flows = create_test_flows(config_yaml)
    flow = flows[0]

    # Send a list of 100 items
    list_100 = []
    for i in range(100):
        list_100.append({"num": i})
    message = Message(payload={"my_list": list_100})
    send_message_to_flow(flow, message)

    # Get the output messages
    for i in range(100):
        output_message = get_message_from_flow(flow)
        assert output_message.get_data("previous") == {"num": i}

    # Clean up
    dispose_connector(connector)
