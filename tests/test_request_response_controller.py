import sys
import pytest
from unittest.mock import MagicMock

sys.path.append("src")

from solace_ai_connector.test_utils.utils_for_test_files import (
    create_test_flows,
    dispose_connector,
    send_message_to_flow,
    get_message_from_flow,
)
from solace_ai_connector.common.message import Message
from solace_ai_connector.flow.request_response_controller import RequestResponseController


def test_request_response_controller_basic():
    """Test basic functionality of the RequestResponseController"""
    config_yaml = """
log:
  log_file_level: DEBUG
  log_file: solace_ai_connector.log
flows:
  - name: request_flow
    components:
      - component_name: requester
        component_module: pass_through
        request_response_controllers:
          test_controller:
            flow_name: response_flow
            timeout_ms: 5000
  - name: response_flow
    components:
      - component_name: responder
        component_module: pass_through
"""
    connector, flows = create_test_flows(config_yaml)
    request_flow, response_flow = flows

    try:
        # Mock the send_message_to_flow method of the connector
        connector.send_message_to_flow = MagicMock()

        # Get the RequestResponseController from the requester component
        requester_component = request_flow['flow'].component_groups[0][0]
        controller = requester_component.get_request_response_controller("test_controller")

        assert controller is not None, "RequestResponseController not found"

        # Test sending a message
        request_data = {
            "payload": {"test": "data"},
            "topic": "test/topic",
            "user_properties": {}
        }
        response = controller.send_message(request_data)

        # Check that send_message_to_flow was called with the correct arguments
        connector.send_message_to_flow.assert_called_once()
        call_args = connector.send_message_to_flow.call_args
        assert call_args[0][0] == "response_flow"
        sent_message = call_args[0][1]
        assert sent_message.get_payload() == {"test": "data"}
        assert sent_message.get_topic() == "test/topic"

        # Simulate a response
        response_message = Message(payload={"response": "data"})
        send_message_to_flow(response_flow, response_message)

        # Check the response
        assert response == {"response": "data"}

    finally:
        dispose_connector(connector)


def test_request_response_controller_timeout():
    """Test timeout functionality of the RequestResponseController"""
    config_yaml = """
log:
  log_file_level: DEBUG
  log_file: solace_ai_connector.log
flows:
  - name: request_flow
    components:
      - component_name: requester
        component_module: pass_through
        request_response_controllers:
          test_controller:
            flow_name: response_flow
            timeout_ms: 100  # Very short timeout for testing
  - name: response_flow
    components:
      - component_name: responder
        component_module: pass_through
"""
    connector, flows = create_test_flows(config_yaml)
    request_flow = flows[0]

    try:
        # Get the RequestResponseController from the requester component
        requester_component = request_flow['flow'].component_groups[0][0]
        controller = requester_component.get_request_response_controller("test_controller")

        assert controller is not None, "RequestResponseController not found"

        # Test sending a message
        request_data = {
            "payload": {"test": "data"},
            "topic": "test/topic",
            "user_properties": {}
        }

        with pytest.raises(TimeoutError):
            controller.send_message(request_data)

    finally:
        dispose_connector(connector)


def test_multiple_request_response_controllers():
    """Test multiple RequestResponseControllers in a single component"""
    config_yaml = """
log:
  log_file_level: DEBUG
  log_file: solace_ai_connector.log
flows:
  - name: request_flow
    components:
      - component_name: requester
        component_module: pass_through
        request_response_controllers:
          controller1:
            flow_name: response_flow1
            timeout_ms: 5000
          controller2:
            flow_name: response_flow2
            timeout_ms: 5000
  - name: response_flow1
    components:
      - component_name: responder1
        component_module: pass_through
  - name: response_flow2
    components:
      - component_name: responder2
        component_module: pass_through
"""
    connector, flows = create_test_flows(config_yaml)
    request_flow, response_flow1, response_flow2 = flows

    try:
        # Mock the send_message_to_flow method of the connector
        connector.send_message_to_flow = MagicMock()

        # Get the RequestResponseControllers from the requester component
        requester_component = request_flow['flow'].component_groups[0][0]
        controller1 = requester_component.get_request_response_controller("controller1")
        controller2 = requester_component.get_request_response_controller("controller2")

        assert controller1 is not None, "RequestResponseController 1 not found"
        assert controller2 is not None, "RequestResponseController 2 not found"

        # Test sending messages to both controllers
        request_data = {
            "payload": {"test": "data"},
            "topic": "test/topic",
            "user_properties": {}
        }

        controller1.send_message(request_data)
        controller2.send_message(request_data)

        # Check that send_message_to_flow was called twice with different flow names
        assert connector.send_message_to_flow.call_count == 2
        call_args_list = connector.send_message_to_flow.call_args_list
        assert call_args_list[0][0][0] == "response_flow1"
        assert call_args_list[1][0][0] == "response_flow2"

    finally:
        dispose_connector(connector)
