import sys

sys.path.append("src")

from solace_ai_connector.test_utils.utils_for_test_files import (
    create_test_flows,
    dispose_connector,
    send_message_to_flow,
    get_message_from_flow,
)
from solace_ai_connector.common.message import Message


def test_request_response_flow_controller_basic():
    """Test basic functionality of the RequestResponseFlowController"""

    def test_invoke_handler(component, message, _data):
        # Call the request_response
        message = component.do_broker_request_response(message)
        try:
            assert message.get_data("previous") == {
                "payload": {"text": "Hello, World!"},
                "topic": None,
                "user_properties": {},
            }
        except AssertionError as e:
            return e
        return "Pass"

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
                        "broker_request_response": {
                            "enabled": True,
                            "broker_config": {
                                "broker_type": "test",
                                "broker_url": "test",
                                "broker_username": "test",
                                "broker_password": "test",
                                "broker_vpn": "test",
                                "payload_encoding": "utf-8",
                                "payload_format": "json",
                            },
                            "request_expiry_ms": 500000,
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

        result = output_message.get_data("previous")

        # if the result is an AssertionError, then raise it
        if isinstance(result, AssertionError):
            raise result

        assert result == "Pass"

    except Exception as e:
        print(e)
        assert False

    finally:
        dispose_connector(connector)


# Test simple streaming request response
# Use the iterate component to break a single message into multiple messages
def test_request_response_flow_controller_streaming():
    """Test streaming functionality of the RequestResponseFlowController"""

    def test_invoke_handler(component, message, data):
        result = []
        for message, last_message in component.do_broker_request_response(
            message, stream=True, streaming_complete_expression="input.payload:last"
        ):
            payload = message.get_data("input.payload")
            result.append(payload)
            if last_message:
                assert payload == {"text": "Chunk3", "last": True}

        assert result == [
            {"text": "Chunk1", "last": False},
            {"text": "Chunk2", "last": False},
            {"text": "Chunk3", "last": True},
        ]

        return "Pass"

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
                        "broker_request_response": {
                            "enabled": True,
                            "broker_config": {
                                "broker_type": "test_streaming",
                                "broker_url": "test",
                                "broker_username": "test",
                                "broker_password": "test",
                                "broker_vpn": "test",
                                "payload_encoding": "utf-8",
                                "payload_format": "json",
                            },
                            "request_expiry_ms": 500000,
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
        send_message_to_flow(
            test_flow,
            Message(
                payload=[
                    {"text": "Chunk1", "last": False},
                    {"text": "Chunk2", "last": False},
                    {"text": "Chunk3", "last": True},
                ]
            ),
        )

        # Get the output message
        output_message = get_message_from_flow(test_flow)

        assert output_message.get_data("previous") == "Pass"

    except Exception as e:
        print(e)
        assert False

    finally:
        dispose_connector(connector)


# Test the timeout functionality
def test_request_response_flow_controller_timeout():
    """Test timeout functionality of the RequestResponseFlowController"""

    def test_invoke_handler(component, message, data):
        # # Call the request_response_flow
        # data_iter = component.send_request_response_flow_message(
        #     "test_controller", message, {"test": "data"}
        # )

        # # This will timeout
        # try:
        #     for message, data, _last_message in data_iter():
        #         assert message.get_data("previous") == {"test": "data"}
        #         assert message.get_data("input.payload") == {"text": "Hello, World!"}
        # except TimeoutError:
        #     return "timeout"
        # return "done"

        # Do it the new way
        try:
            for message, _last_message in component.do_broker_request_response(
                message, stream=True, streaming_complete_expression="input.payload:last"
            ):
                pass
        except TimeoutError:
            return "Timeout"
        return "Fail"

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
                        "broker_request_response": {
                            "enabled": True,
                            "broker_config": {
                                "broker_type": "test_streaming",
                                "broker_url": "test",
                                "broker_username": "test",
                                "broker_password": "test",
                                "broker_vpn": "test",
                                "payload_encoding": "utf-8",
                                "payload_format": "json",
                            },
                            "request_expiry_ms": 2000,
                        },
                    }
                ],
            },
        ]
    }
    connector, flows = create_test_flows(config)

    test_flow = flows[0]

    try:

        # Send a message with an empty list in the payload to the test_streaming broker type
        # This will not send any chunks and should timeout
        send_message_to_flow(test_flow, Message(payload=[]))

        # Get the output message
        output_message = get_message_from_flow(test_flow)

        assert output_message.get_data("previous") == "Timeout"

    finally:
        dispose_connector(connector)
