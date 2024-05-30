"""Some tests to verify the filter component works as expected"""

# import pytest

from utils_for_test_files import (
    create_test_flows,
    # create_connector,
    dispose_connector,
    # send_and_receive_message_on_flow,
    send_message_to_flow,
    get_message_from_flow,
)
from solace_ai_connector.common.message import Message

# from solace_ai_connector.common.log import log


def test_simple_filter():
    """Test the filter component with a simple expression"""
    config_yaml = """
log:
  log_file_level: DEBUG
  log_file: solace_ai_connector.log
flows:
  - name: test_flow
    components:
      - component_name: message_filter
        component_module: message_filter
        component_config:
          filter_expression:
            invoke:
              module: invoke_functions
              function: equal
              params:
                positional:
                  - source_expression(input.payload:my_list.1)
                  - 2
"""
    connector, flows = create_test_flows(config_yaml)
    flow = flows[0]

    # Send 3 messages - the first and last should be sent
    message = Message(payload={"my_list": [1, 2, 3]})
    send_message_to_flow(flow, message)
    message = Message(payload={"my_list": [4, 5, 6]})
    send_message_to_flow(flow, message)
    message = Message(payload={"my_list": [3, 2, 1]})
    send_message_to_flow(flow, message)

    # Expect two messages to be sent
    output_message = get_message_from_flow(flow)
    assert output_message.get_data("input.payload:my_list") == [1, 2, 3]

    output_message = get_message_from_flow(flow)
    assert output_message.get_data("input.payload:my_list") == [3, 2, 1]

    # Clean up
    dispose_connector(connector)


def test_missing_item_filter():
    """Test the filter component with data items that are missing"""
    config_yaml = """
log:
  log_file_level: DEBUG
  log_file: solace_ai_connector.log
flows:
  - name: test_flow
    components:
      - component_name: message_filter
        component_module: message_filter
        component_config:
          filter_expression:
            invoke:
              module: invoke_functions
              function: not_equal
              params:
                positional:
                  - source_expression(input.payload:my_list)
                  - null
"""
    connector, flows = create_test_flows(config_yaml)
    flow = flows[0]

    # Send 2 messages
    message = Message(payload={"my_list": [1, 2, 3], "my_obj": {"a": 1, "b": 2}})
    send_message_to_flow(flow, message)
    message = Message(payload={"my_obj": {"a": 1, "b": 2}})
    send_message_to_flow(flow, message)
    message = Message(payload={"my_list": [3, 2, 1], "my_obj": {"a": 1, "b": 2}})
    send_message_to_flow(flow, message)

    # Expect two messages to be sent
    output_message = get_message_from_flow(flow)
    assert output_message.get_data("input.payload:my_list") == [1, 2, 3]

    output_message = get_message_from_flow(flow)
    assert output_message.get_data("input.payload:my_list") == [3, 2, 1]

    # Clean up
    dispose_connector(connector)
