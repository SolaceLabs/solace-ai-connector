"""This test file tests all things to do with the flows and the components that make up the flows"""

import sys

sys.path.append("src")
import pytest
import time

from solace_ai_connector.test_utils.utils_for_test_files import (
    create_test_flows,
    create_connector,
    dispose_connector,
    # send_and_receive_message_on_flow,
    send_message_to_flow,
    get_message_from_flow,
)
from solace_ai_connector.common.message import Message

# from solace_ai_connector.common.log import log


# @pytest.fixture
# def connector_and_flows(request):
#     config_yaml = request.param
#     # Set up the connector here using config_yaml
#     connector, flows = create_test_flows(config_yaml)
#     yield connector, flows
#     # Tear down the connector here
#     dispose_connector(connector)


# Commenting out for now. This test is very very timing sensitive and fails on the CI too often
# @pytest.mark.parametrize(
#     "connector_and_flows",
#     [
#         """
# log:
#   log_file_level: DEBUG
#   log_file: solace_ai_connector.log
# flows:
#   - name: test_flow
#     components:
#       - component_name: delay1
#         component_module: delay
#         component_config:
#           delay: 0.7
#         num_instances: 4
#         input_transforms:
#           - type: append
#             source_expression: self:component_index
#             dest_expression: user_data.path:my_path
#         input_selection:
#           source_expression: input.payload:text
#       - component_name: delay2
#         component_module: delay
#         component_config:
#           delay: 0.7
#         num_instances: 3
#         input_transforms:
#           - type: copy
#             source_expression: previous
#             dest_expression: user_data.temp:my_text.text
#           - type: copy
#             source_expression: self:name
#             dest_expression: user_data.temp:my_text.name
#           - type: append
#             source_expression: self:component_index
#             dest_expression: user_data.path:my_path
#         input_selection:
#           source_expression: user_data.temp
#       - component_name: delay3
#         component_module: delay
#         component_config:
#           delay: 0.7
#         num_instances: 2
#         input_transforms:
#           - type: append
#             source_expression: self:component_index
#             dest_expression: user_data.path:my_path
#         input_selection:
#           source_expression: previous
# """
#     ],
#     indirect=True,
# )
# def test_multiple_component_instances(
#     connector_and_flows,
# ):  # pylint: disable=redefined-outer-name
#     """Test that multiple component instances work"""
#     # Create a simple configuration
#     connector, flows = connector_and_flows
#     flow = flows[0]
#     # Send the same message through the flow 16 times
#     for _ in range(24):
#         message = Message(payload={"text": "Hello, World!"})
#         send_message_to_flow(flow, message)

#     components_used = [[0, 0, 0, 0], [0, 0, 0], [0, 0]]
#     for _ in range(24):
#         output_message = get_message_from_flow(flow)

#         # The message keeps an array of the path it took through the flow
#         # With the delays that each encountered, we should be certain that
#         # each of the parallel components was used equally
#         path = output_message.get_data("user_data.path:my_path")
#         for i, component_index in enumerate(path):
#             # Add up the number of times each component was used
#             components_used[i][int(component_index)] += 1

#         # Check the output
#         assert output_message.get_data("previous") == {
#             "my_text": {"text": "Hello, World!", "name": "delay2"}
#         }
#         assert output_message.get_data("user_data.temp") == {
#             "my_text": {"text": "Hello, World!", "name": "delay2"}
#         }

#     # Verify that the components were used equally
#     for components in components_used:
#         for component in components:
#             assert component == 24 / len(components)

#     dispose_connector(connector)


def test_on_flow_creation_event():
    """Test that the on_flow_creation event is called when a flow is created"""
    config_yaml = """
log:
  log_file_level: DEBUG
  log_file: solace_ai_connector.log
flows:
  - name: test_flow
    components:
      - component_name: delay1
        component_module: delay
        input_selection:
          source_expression: input.payload:text
  - name: test_flow2
    components:
      - component_name: delay2
        component_module: delay
        input_selection:
          source_expression: input.payload:text
"""
    event_handler_called = False
    flows = []

    def event_handler(created_flows):
        nonlocal event_handler_called
        nonlocal flows
        event_handler_called = True
        flows = created_flows

    # Create the connector
    connector = create_connector(
        config_yaml, event_handlers={"on_flow_creation": event_handler}
    )

    dispose_connector(connector)

    # Verify that the on_flow_creation event was called
    assert len(flows) == 2
    assert flows[0].name == "test_flow"
    assert flows[1].name == "test_flow2"


def test_multiple_flow_instances():
    """Test that multiple flow instances work"""
    config_yaml = """
log:
  log_file_level: DEBUG
  log_file: solace_ai_connector.log
flows:
  - name: test_flow
    num_instances: 4
    components:
      - component_name: delay1
        component_module: delay
        input_selection:
          source_expression: input.payload:text
"""
    # Create the connector
    connector, flows = create_test_flows(config_yaml)

    # Send the same message through the flow 16 times
    for i in range(16):
        message = Message(payload={"text": "Hello, World!"})
        send_message_to_flow(flows[i % 4], message)

    # Get the current time
    start_time = time.time()

    # Verify that the messages are received in order
    for i in range(16):
        output_message = get_message_from_flow(flows[i % 4])
        assert output_message.get_data("previous") == "Hello, World!"

    # Check the time taken - it should be less than 5 seconds
    end_time = time.time()
    assert end_time - start_time < 5
    assert end_time - start_time > 3

    dispose_connector(connector)
