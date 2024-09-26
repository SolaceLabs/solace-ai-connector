"""Some tests to verify the aggregate component works as expected"""

import sys

sys.path.append("src")
import time

from solace_ai_connector.test_utils.utils_for_test_files import (
    create_test_flows,
    dispose_connector,
    send_message_to_flow,
    get_event_from_flow,
    get_message_from_flow,
)
from solace_ai_connector.common.message import Message
from solace_ai_connector.common.event import EventType


def test_aggregate_by_time():
    """Test the aggregate component by time"""
    TIMEOUT_MS = 700
    config_yaml = f"""
log:
  log_file_level: DEBUG
  log_file: solace_ai_connector.log
flows:
  - name: test_flow
    components:
      - component_name: aggregate
        component_module: aggregate
        component_config:
          max_items: 10
          max_time_ms: {TIMEOUT_MS}
        input_selection:
          source_expression: input.payload
"""
    connector, flows = create_test_flows(config_yaml)
    flow = flows[0]

    try:
        for i in range(2):
            for j in range(3):
                message = Message(payload={"text": f"Hello, World! {i} {j}"})
                send_message_to_flow(flow, message)

            start_time = time.time()

            # Get the output message
            event = get_event_from_flow(flow)

            end_time = time.time()

            # Check that the time it took is within a reasonable range
            assert abs((end_time - start_time) - (TIMEOUT_MS / 1000)) < 0.05

            # Expected value
            expected = []
            for j in range(3):
                expected.append({"text": f"Hello, World! {i} {j}"})

            # Check the output
            assert event.event_type == EventType.MESSAGE
            assert event.data.get_data("previous") == expected

    finally:
        # Tear down the connector
        dispose_connector(connector)


def test_aggregate_by_items():
    """Test the aggregate component by items"""
    config_yaml = """
log:
  log_file_level: DEBUG
  log_file: solace_ai_connector.log
flows:
  - name: test_flow
    components:
      - component_name: aggregate
        component_module: aggregate
        component_config:
          max_items: 3
          max_time_ms: 1000
        input_selection:
          source_expression: input.payload
"""
    connector, flows = create_test_flows(config_yaml)
    flow = flows[0]

    try:
        for i in range(2):
            start_time = time.time()
            for j in range(3):
                message = Message(payload={"text": f"Hello, World! {i} {j}"})
                send_message_to_flow(flow, message)

            # Get the output event
            message = get_message_from_flow(flow)

            end_time = time.time()

            # Check that the time it took is within a reasonable range
            assert (end_time - start_time) < 0.05

            # Expected value
            expected = []
            for j in range(3):
                expected.append({"text": f"Hello, World! {i} {j}"})

            # Check the output
            assert message.get_data("previous") == expected
    finally:
        # Tear down the connector
        dispose_connector(connector)


def test_both_items_and_time():
    """Test the aggregate component by items"""
    MAX_TIME_MS = 1000
    config_yaml = f"""
log:
  log_file_level: DEBUG
  log_file: solace_ai_connector.log
flows:
  - name: test_flow
    components:
      - component_name: aggregate
        component_module: aggregate
        component_config:
          max_items: 3
          max_time_ms: {MAX_TIME_MS}
        input_selection:
          source_expression: input.payload
"""
    connector, flows = create_test_flows(config_yaml)
    flow = flows[0]

    # We will send 10 messages. We should get 4 messages out, 3 due to max_items
    # and 1 due to max_time_ms

    start_time = time.time()
    expected = []
    try:
        for j in range(10):
            message = Message(payload={"text": f"Hello, World! {j}"})
            expected.append({"text": f"Hello, World! {j}"})
            send_message_to_flow(flow, message)

        for j in range(4):
            if j < 3:
                # Get the next 3 expected messages
                event = get_event_from_flow(flow)
                end_time = time.time()
                assert event.event_type == EventType.MESSAGE
                assert event.data.get_data("previous") == expected[j * 3 : j * 3 + 3]
                # assert (end_time - start_time) < 0.1
            else:
                # Get the last expected message
                event = get_event_from_flow(flow)
                end_time = time.time()
                assert abs((end_time - start_time) - (MAX_TIME_MS / 1000)) < 0.1
                assert event.event_type == EventType.MESSAGE
                assert event.data.get_data("previous") == expected[j * 3 :]

    finally:
        # Tear down the connector
        dispose_connector(connector)
