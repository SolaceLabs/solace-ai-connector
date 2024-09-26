"""Some tests to verify the filter component works as expected"""

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
                  - evaluate_expression(input.payload:my_list.1)
                  - 2
"""
    connector, flows = create_test_flows(config_yaml)
    flow = flows[0]

    try:
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
    finally:
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
                  - evaluate_expression(input.payload:my_list)
                  - null
"""
    connector, flows = create_test_flows(config_yaml)
    try:
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
    finally:
        # Clean up
        dispose_connector(connector)


def test_filter_with_multi_stage_data():
    """Test the filter component with a previous stage passing on data and the filter
    input_transforms copying that data into a user_data area"""
    config_yaml = """
log:
  log_file_level: DEBUG
  log_file: solace_ai_connector.log
flows:
  - name: test_flow
    components:
      - component_name: user_processor
        component_module: user_processor
        component_config:
          component_processing:
            invoke:
              module: invoke_functions
              function: add
              params:
                positional:
                  - 5
                  - 6
      - component_name: message_filter
        component_module: message_filter
        component_config:
          filter_expression:
            invoke:
              module: invoke_functions
              function: not_equal
              params:
                positional:
                  - 1
                  - 2
        input_transforms:
          - type: copy
            source_expression: previous
            dest_expression: user_data.output
      - component_name: pass_through
        component_module: pass_through


"""
    connector, flows = create_test_flows(config_yaml, queue_timeout=1)
    flow = flows[0]

    # Send 1 message
    message = Message(payload={"my_list": [1, 2, 3], "my_obj": {"a": 1, "b": 2}})
    send_message_to_flow(flow, message)

    # Expect a message
    try:
        output_message = get_message_from_flow(flow)
        assert output_message.get_data("input.payload:my_list") == [1, 2, 3]
        assert output_message.get_data("user_data.output") == 11
    finally:
        # Clean up
        dispose_connector(connector)


def test_filter_with_multi_stage_data_with_timer_input():
    """Test the filter component with a previous stage passing on data and the filter
    input_transforms copying that data into a user_data area - this time with a timer causing the message to be sent
    """
    config_yaml = """
log:
  log_file_level: DEBUG
  log_file: solace_ai_connector.log
trace:
  trace_file: solace_ai_connector.trace
flows:
  - name: test_flow
    components:
      - component_name: timer_input
        component_module: timer_input
        component_config:
          interval_ms: 500
          skip_messages_if_behind: false
      - component_name: user_processor
        component_module: user_processor
        component_config:
          component_processing:
            invoke:
              module: invoke_functions
              function: add
              params:
                positional:
                  - 5
                  - 6
      - component_name: message_filter
        component_module: message_filter
        component_config:
          filter_expression:
            invoke:
              module: invoke_functions
              function: not_equal
              params:
                positional:
                  - 1
                  - 2
        input_transforms:
          - type: copy
            source_expression: previous
            dest_expression: user_data.output
      - component_name: pass_through
        component_module: pass_through


"""
    connector, flows = create_test_flows(config_yaml, queue_timeout=3)
    flow = flows[0]

    try:
        # Get the output messages (should be at least 3 seconds worth)
        for _ in range(3):
            msg = get_message_from_flow(flow)
            assert msg.get_data("user_data.output") == 11
    finally:
        # Clean up
        dispose_connector(connector)
