"""This file contains tests for for memory and file storage"""

import sys
import os

# import queue

sys.path.append("src")

from utils_for_test_files import (  # pylint: disable=wrong-import-position
    create_test_flows,
    # create_and_run_component,
    dispose_connector,
    send_message_to_flow,
    get_message_from_flow,
)
from solace_ai_connector.common.message import (  # pylint: disable=wrong-import-position
    Message,
)


def test_memory_storage():
    """Test the memory storage"""
    # Create a simple configuration
    config_yaml = """
instance_name: test_instance
log:
  log_file_level: DEBUG
  log_file: solace_ai_connector.log
storage:
  - name: memory
    storage_type: memory
flows:
  # This will fail with the specified error
  - name: flow
    components:
      - component_name: storage_tester
        component_module: storage_tester
        component_config:
          storage_name: memory
        component_input:
          source_expression: input.payload

"""
    connector, flows = create_test_flows(config_yaml)
    flow = flows[0]

    # Send a message to the input flow
    send_message_to_flow(flow, Message(payload={"test_value": "second_value"}))
    output_message = get_message_from_flow(flow)
    assert output_message.get_data("previous") == {"test_value": "initial_value"}

    send_message_to_flow(flow, Message(payload={"test_value": "third_value"}))
    output_message = get_message_from_flow(flow)
    assert output_message.get_data("previous") == {"test_value": "second_value"}

    dispose_connector(connector)


def test_file_storage():
    """Test the file storage"""
    # Create a simple configuration
    config_yaml = """
instance_name: test_instance
log:
  log_file_level: DEBUG
  log_file: solace_ai_connector.log
storage:
  - name: file
    storage_type: file
    storage_config:
      file: test_storage.json
flows:
  # This will fail with the specified error
  - name: flow
    components:
      - component_name: storage_tester
        component_module: storage_tester
        component_config:
          storage_name: file
        component_input:
          source_expression: input.payload

"""
    # If the file exists, delete it
    if os.path.exists("test_storage.json"):
        os.remove("test_storage.json")

    connector, flows = create_test_flows(config_yaml)
    flow = flows[0]

    # Send a message to the input flow
    send_message_to_flow(flow, Message(payload={"test_value": "second_value"}))
    output_message = get_message_from_flow(flow)
    assert output_message.get_data("previous") == {"test_value": "initial_value"}

    send_message_to_flow(flow, Message(payload={"test_value": "third_value"}))
    output_message = get_message_from_flow(flow)
    assert output_message.get_data("previous") == {"test_value": "second_value"}

    dispose_connector(connector)

    os.remove("test_storage.json")
