import sys
import pytest

sys.path.append("src")

from solace_ai_connector.common.message import Message
from solace_ai_connector.test_utils.utils_for_test_files import (
    create_test_flows,
    dispose_connector,
)
from solace_ai_connector.common.exceptions import (
    SessionNotFoundError,
    SessionLimitExceededError,
)
from solace_ai_connector.components.inputs_outputs.broker_request_response import (
    BrokerRequestResponse,
    DEFAULT_REPLY_METADATA_KEY,
    DEFAULT_REPLY_TOPIC_KEY,
)


def test_multi_session_lifecycle_and_isolation():
    """
    Tests the basic lifecycle of multi-session request/response:
    - Session creation
    - Independent usage
    - Listing active sessions
    - Session destruction
    - Error on using a destroyed session
    """
    config = {
        "flows": [
            {
                "name": "test_multi_session_flow",
                "components": [
                    {
                        "component_name": "session_handler",
                        "component_module": "handler_callback",
                        "multi_session_request_response": {
                            "enabled": True,
                            "default_broker_config": {
                                "broker_type": "test",
                                "broker_url": "test",
                                "broker_username": "test",
                                "broker_password": "test",
                                "broker_vpn": "test",
                            },
                        },
                    }
                ],
            }
        ]
    }

    connector, flows = create_test_flows(config)
    # Get the component instance directly to call its API
    component = flows[0]["flow"].component_groups[0][0]

    try:
        # 1. Create two sessions
        session_id_A = component.create_request_response_session()
        session_id_B = component.create_request_response_session(
            session_config={
                "request_expiry_ms": 60000
            }  # Custom config for this session
        )
        assert session_id_A != session_id_B

        # 2. Use both sessions independently
        message_A = Message(payload={"data": "A"})
        response_A = component.do_broker_request_response(
            message_A, session_id=session_id_A
        )
        assert response_A.get_payload() == {"data": "A"}

        message_B = Message(payload={"data": "B"})
        response_B = component.do_broker_request_response(
            message_B, session_id=session_id_B
        )
        assert response_B.get_payload() == {"data": "B"}

        # 3. List sessions and verify status
        sessions = component.list_request_response_sessions()
        assert len(sessions) == 2
        session_ids_from_list = {s["session_id"] for s in sessions}
        assert session_ids_from_list == {session_id_A, session_id_B}
        for s in sessions:
            assert s["active_request_count"] == 0

        # 4. Destroy one session
        assert component.destroy_request_response_session(session_id_A) is True
        sessions_after_destroy = component.list_request_response_sessions()
        assert len(sessions_after_destroy) == 1
        assert sessions_after_destroy[0]["session_id"] == session_id_B

        # 5. Verify error on using destroyed session
        with pytest.raises(SessionNotFoundError):
            component.do_broker_request_response(message_A, session_id=session_id_A)

        # 6. Verify the other session is still functional
        response_B_again = component.do_broker_request_response(
            message_B, session_id=session_id_B
        )
        assert response_B_again.get_payload() == {"data": "B"}
        # Also verify that the internal user properties were cleaned up
        user_props = response_B_again.get_user_properties()
        assert DEFAULT_REPLY_METADATA_KEY not in user_props
        assert DEFAULT_REPLY_TOPIC_KEY not in user_props

        # 7. Destroy the second session
        assert component.destroy_request_response_session(session_id_B) is True
        assert len(component.list_request_response_sessions()) == 0

    finally:
        dispose_connector(connector)


def test_fire_and_forget_sends_message():
    """
    Tests that do_broker_request_response with wait_for_response=False
    correctly sends the message (fire-and-forget).
    """
    config = {
        "flows": [
            {
                "name": "test_fire_and_forget_flow",
                "components": [
                    {
                        "component_name": "session_handler",
                        "component_module": "handler_callback",
                        "multi_session_request_response": {
                            "enabled": True,
                            "default_broker_config": {
                                "broker_type": "test",
                                "broker_url": "test",
                                "broker_username": "test",
                                "broker_password": "test",
                                "broker_vpn": "test",
                            },
                        },
                    }
                ],
            }
        ]
    }

    connector, flows = create_test_flows(config)
    component = flows[0]["flow"].component_groups[0][0]

    try:
        # 1. Create a session
        session_id = component.create_request_response_session()

        # 2. Spy on the send_message method of the controller
        with unittest.mock.patch(
            "solace_ai_connector.flow.request_response_flow_controller.RequestResponseFlowController.send_message"
        ) as mock_send:
            # 3. Call fire-and-forget
            ff_message = Message(payload={"data": "fire_and_forget_sync"})
            response = component.do_broker_request_response(
                ff_message, session_id=session_id, wait_for_response=False
            )

            # 4. Assert that the call returned None and send_message was called
            assert response is None
            mock_send.assert_called_once()

        # 5. Destroy the session
        component.destroy_request_response_session(session_id)

    finally:
        dispose_connector(connector)


@pytest.mark.asyncio
async def test_async_multi_session_lifecycle():
    """
    Tests the async version of do_broker_request_response with the multi-session manager.
    """
    config = {
        "flows": [
            {
                "name": "test_async_multi_session_flow",
                "components": [
                    {
                        "component_name": "session_handler",
                        "component_module": "handler_callback",
                        "multi_session_request_response": {
                            "enabled": True,
                            "default_broker_config": {
                                "broker_type": "test",
                                "broker_url": "test",
                                "broker_username": "test",
                                "broker_password": "test",
                                "broker_vpn": "test",
                            },
                        },
                    }
                ],
            }
        ]
    }

    connector, flows = create_test_flows(config)
    component = flows[0]["flow"].component_groups[0][0]

    try:
        # 1. Create a session
        session_id = component.create_request_response_session()
        assert session_id is not None

        # 2. Use the session with the async method (blocking wait)
        message = Message(payload={"data": "async_test"})
        response = await component.do_broker_request_response_async(
            message, session_id=session_id
        )
        assert response.get_payload() == {"data": "async_test"}

        # 3. Test fire-and-forget async
        ff_message = Message(payload={"data": "fire_and_forget"})
        ff_response = await component.do_broker_request_response_async(
            ff_message, session_id=session_id, wait_for_response=False
        )
        assert ff_response is None

        # 4. Destroy the session
        assert component.destroy_request_response_session(session_id) is True

        # 5. Verify error on using destroyed session with async method
        with pytest.raises(SessionNotFoundError):
            await component.do_broker_request_response_async(
                message, session_id=session_id
            )

    finally:
        dispose_connector(connector)


@pytest.mark.asyncio
async def test_async_multi_session_streaming():
    """
    Tests the async version of do_broker_request_response with streaming.
    """
    config = {
        "flows": [
            {
                "name": "test_async_streaming_flow",
                "components": [
                    {
                        "component_name": "session_handler",
                        "component_module": "handler_callback",
                        "multi_session_request_response": {
                            "enabled": True,
                            "default_broker_config": {
                                "broker_type": "test_streaming",
                                "broker_url": "test",
                                "broker_username": "test",
                                "broker_password": "test",
                                "broker_vpn": "test",
                            },
                        },
                    }
                ],
            }
        ]
    }

    connector, flows = create_test_flows(config)
    component = flows[0]["flow"].component_groups[0][0]

    try:
        session_id = component.create_request_response_session()

        request_payload = [
            {"text": "chunk1", "done": False},
            {"text": "chunk2", "done": False},
            {"text": "chunk3", "done": True},
        ]
        message = Message(payload=request_payload, topic="test/stream")

        response_generator = await component.do_broker_request_response_async(
            message,
            session_id=session_id,
            stream=True,
            streaming_complete_expression="input.payload:done",
        )

        results = []
        for chunk, is_last in response_generator:
            results.append(chunk.get_payload())
            if is_last:
                break

        assert len(results) == 3
        assert results[0]["text"] == "chunk1"
        assert results[2]["text"] == "chunk3"
        assert results[2]["done"] is True

        component.destroy_request_response_session(session_id)

    finally:
        dispose_connector(connector)


def test_multi_session_no_default_config():
    """
    Tests that multi-session mode works without a default broker config.
    - Fails to create a session without overrides.
    - Succeeds in creating a session with full overrides.
    - The created session is functional.
    """
    config = {
        "flows": [
            {
                "name": "test_no_default_flow",
                "components": [
                    {
                        "component_name": "session_handler",
                        "component_module": "handler_callback",
                        "multi_session_request_response": {
                            "enabled": True
                            # NO default_broker_config here
                        },
                    }
                ],
            }
        ]
    }

    connector, flows = create_test_flows(config)
    component = flows[0]["flow"].component_groups[0][0]

    try:
        # 1. Verify creating a session with NO overrides fails
        with pytest.raises(
            ValueError, match="must contain a 'broker_config' dictionary"
        ):
            component.create_request_response_session()

        # 2. Create a session WITH a full broker_config override
        session_id = component.create_request_response_session(
            session_config={
                "broker_config": {
                    "broker_type": "test",
                    "broker_url": "test",
                    "broker_username": "test",
                    "broker_password": "test",
                    "broker_vpn": "test",
                }
            }
        )
        assert session_id is not None
        assert len(component.list_request_response_sessions()) == 1

        # 3. Verify the session is functional
        message = Message(payload={"data": "no_default_test"})
        response = component.do_broker_request_response(message, session_id=session_id)
        assert response.get_payload() == {"data": "no_default_test"}

        # 4. Destroy the session
        assert component.destroy_request_response_session(session_id) is True
        assert len(component.list_request_response_sessions()) == 0

    finally:
        dispose_connector(connector)


def test_max_sessions_limit():
    """Tests that the max_sessions limit is enforced."""
    config = {
        "flows": [
            {
                "name": "test_max_sessions_flow",
                "components": [
                    {
                        "component_name": "session_handler",
                        "component_module": "handler_callback",
                        "multi_session_request_response": {
                            "enabled": True,
                            "max_sessions": 2,  # Set a low limit
                            "default_broker_config": {
                                "broker_type": "test",
                                "broker_url": "test",
                                "broker_username": "test",
                                "broker_password": "test",
                                "broker_vpn": "test",
                            },
                        },
                    }
                ],
            }
        ]
    }

    connector, flows = create_test_flows(config)
    component = flows[0]["flow"].component_groups[0][0]

    try:
        # 1. Create sessions up to the limit
        session_id_1 = component.create_request_response_session()
        component.create_request_response_session()
        assert len(component.list_request_response_sessions()) == 2

        # 2. Verify that creating one more session raises an error
        with pytest.raises(SessionLimitExceededError):
            component.create_request_response_session()

        # 3. Destroy a session and verify a new one can be created
        component.destroy_request_response_session(session_id_1)
        assert len(component.list_request_response_sessions()) == 1
        component.create_request_response_session()
        assert len(component.list_request_response_sessions()) == 2

    finally:
        dispose_connector(connector)


import unittest.mock


def test_backward_compatibility_with_legacy_rrc():
    """
    Tests that do_broker_request_response works correctly with the legacy,
    component-level RRC configuration when no session_id is provided.
    """
    config = {
        "flows": [
            {
                "name": "test_legacy_flow",
                "components": [
                    {
                        "component_name": "legacy_requester",
                        "component_module": "handler_callback",
                        # NOTE: No multi_session_request_response block
                        "broker_request_response": {
                            "enabled": True,
                            "broker_config": {
                                "broker_type": "test",
                                "broker_url": "test",
                                "broker_username": "test",
                                "broker_password": "test",
                                "broker_vpn": "test",
                            },
                        },
                    }
                ],
            }
        ]
    }

    connector, flows = create_test_flows(config)
    component = flows[0]["flow"].component_groups[0][0]

    try:
        # Call do_broker_request_response WITHOUT a session_id
        message = Message(payload={"data": "legacy_test"})
        response = component.do_broker_request_response(message)

        # Verify the response is correct, proving the fallback worked
        assert response.get_payload() == {"data": "legacy_test"}

    finally:
        dispose_connector(connector)


def test_rrc_process_response_with_decode_error():
    """
    Unit tests the process_response method of BrokerRequestResponse
    to ensure it handles payload decode errors correctly.
    """
    # 1. Create an instance of the component to test, mocking dependencies
    with (
        unittest.mock.patch(
            "solace_ai_connector.components.inputs_outputs.broker_request_response.BrokerRequestResponse.connect"
        ),
        unittest.mock.patch(
            "solace_ai_connector.components.inputs_outputs.broker_request_response.BrokerRequestResponse.start"
        ),
    ):
        rrc = BrokerRequestResponse(
            config={
                "component_config": {
                    "payload_format": "json",
                    "user_properties_reply_metadata_key": "test_meta_key",
                    "user_properties_reply_topic_key": "test_topic_key",
                    # Add dummy broker config to pass validation
                    "broker_url": "dummy_url",
                    "broker_username": "dummy_user",
                    "broker_password": "dummy_password",
                    "broker_vpn": "dummy_vpn",
                }
            },
            cache_service=unittest.mock.MagicMock(),
        )

    # 2. Mock dependencies needed by process_response
    rrc.test_mode = True
    rrc.process_post_invoke = unittest.mock.MagicMock()
    rrc.cache_service.get_data.return_value = {
        "request_id": "123",
        "stream": False,
    }

    # 3. Create a fake response message with a bad payload
    bad_payload = '{"invalid": json}'  # Invalid JSON string
    user_props = {"test_meta_key": '[{"request_id": "123"}]'}
    mock_broker_message = Message(payload=bad_payload, user_properties=user_props)

    # 4. Call the method under test
    rrc.process_response(mock_broker_message)

    # 5. Assert that process_post_invoke was called with the error payload
    rrc.process_post_invoke.assert_called_once()
    call_args = rrc.process_post_invoke.call_args
    response_data = call_args[0][0]  # First positional argument (the 'result' dict)
    message_arg = call_args[0][1]  # Second positional argument (the 'message' object)

    # The payload of the new message should be the error dict
    assert isinstance(message_arg.get_payload(), dict)
    assert message_arg.get_payload()["error"] == "Payload decode error"
    assert "details" in message_arg.get_payload()
    assert "Invalid JSON payload" in message_arg.get_payload()["details"]

    # The 'result' passed to process_post_invoke should also contain the error payload
    assert isinstance(response_data["payload"], dict)
    assert response_data["payload"]["error"] == "Payload decode error"
