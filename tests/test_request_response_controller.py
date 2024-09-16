import sys
import pytest

sys.path.append("src")

from solace_ai_connector.test_utils.utils_for_test_files import (
    create_test_flows,
    dispose_connector,
    send_message_to_flow,
    get_message_from_flow,
)
from solace_ai_connector.common.message import Message
from solace_ai_connector.flow.request_response_controller import (
    RequestResponseFlowController,
)


def test_request_response_flow_controller_basic():
    """Test basic functionality of the RequestResponseFlowController"""

    def test_invoke_handler(component, message, data):
        # Call the request_response_flow
        data_iter = component.send_request_response_flow_message(
            "test_controller", message, {"test": "data"}
        )

        # Just a single message with no streaming
        for message, data in data_iter():
            assert message.get_data("previous") == {"test": "data"}
            assert message.get_data("input.payload") == {"text": "Hello, World!"}

        return "done"

    config = {
        "flows": [
            {
                "name": "test_flow",
                "components": [
                    {
                        "component_name": "requester",
                        "component_module": "handler_callback",
                        "component_config": {
                            "invoke_handler": test_invoke_handler,
                        },
                        "request_response_flow_controllers": [
                            {
                                "name": "test_controller",
                                "flow_name": "request_response_flow",
                                "timeout_ms": 500000,
                            }
                        ],
                    }
                ],
            },
            {
                "name": "request_response_flow",
                "test_ignore": True,
                "components": [
                    {"component_name": "responder", "component_module": "pass_through"}
                ],
            },
        ]
    }
    connector, flows = create_test_flows(config)

    test_flow = flows[0]

    try:

        # Send a message to the input flow
        send_message_to_flow(test_flow, Message(payload={"text": "Hello, World!"}))

        # Get the output message
        output_message = get_message_from_flow(test_flow)

        assert output_message.get_data("previous") == "done"

    finally:
        dispose_connector(connector)


# Test simple streaming request response
# Use the iterate component to break a single message into multiple messages
def test_request_response_controller_streaming():
    """Test streaming functionality of the RequestResponseController"""

    def test_invoke_handler(component, message, data):
        # Call the request_response_flow
        data_iter = component.send_request_response_message(
            "test_controller",
            message,
            [
                {"test": "data1", "streaming": {"last_message": False}},
                {"test": "data2", "streaming": {"last_message": False}},
                {"test": "data3", "streaming": {"last_message": True}},
            ],
        )

        # Expecting 3 messages
        results = []
        for message, data in data_iter():
            results.append(data.get("test"))

        assert results == ["data1", "data2", "data3"]
        return "done"

    config = {
        "flows": [
            {
                "name": "test_flow",
                "components": [
                    {
                        "component_name": "requester",
                        "component_module": "handler_callback",
                        "component_config": {
                            "invoke_handler": test_invoke_handler,
                        },
                        "request_response_controllers": [
                            {
                                "name": "test_controller",
                                "flow_name": "request_response_flow",
                                "streaming": True,
                                "streaming_last_message_expression": "previous:streaming.last_message",
                                "timeout_ms": 500000,
                            }
                        ],
                    }
                ],
            },
            {
                "name": "request_response_flow",
                "test_ignore": True,
                "components": [
                    {"component_name": "responder", "component_module": "iterate"}
                ],
            },
        ]
    }
    connector, flows = create_test_flows(config)

    test_flow = flows[0]

    try:

        # Send a message to the input flow
        send_message_to_flow(test_flow, Message(payload={"text": "Hello, World!"}))

        # Get the output message
        output_message = get_message_from_flow(test_flow)

        assert output_message.get_data("previous") == "done"

    finally:
        dispose_connector(connector)


# Test the timeout functionality
def test_request_response_controller_timeout():
    """Test timeout functionality of the RequestResponseController"""

    def test_invoke_handler(component, message, data):
        # Call the request_response_flow
        data_iter = component.send_request_response_message(
            "test_controller", message, {"test": "data"}
        )

        # This will timeout
        try:
            for message, data in data_iter():
                assert message.get_data("previous") == {"test": "data"}
                assert message.get_data("input.payload") == {"text": "Hello, World!"}
        except TimeoutError:
            return "timeout"
        return "done"

    config = {
        "flows": [
            {
                "name": "test_flow",
                "components": [
                    {
                        "component_name": "requester",
                        "component_module": "handler_callback",
                        "component_config": {
                            "invoke_handler": test_invoke_handler,
                        },
                        "request_response_controllers": [
                            {
                                "name": "test_controller",
                                "flow_name": "request_response_flow",
                                "timeout_ms": 1000,
                            }
                        ],
                    }
                ],
            },
            {
                "name": "request_response_flow",
                "test_ignore": True,
                "components": [
                    {
                        "component_name": "responder",
                        "component_module": "delay",
                        "component_config": {
                            "delay": 5,
                        },
                    }
                ],
            },
        ]
    }
    connector, flows = create_test_flows(config)

    test_flow = flows[0]

    try:

        # Send a message to the input flow
        send_message_to_flow(test_flow, Message(payload={"text": "Hello, World!"}))

        # Get the output message
        output_message = get_message_from_flow(test_flow)

        assert output_message.get_data("previous") == "timeout"

    finally:
        dispose_connector(connector)
