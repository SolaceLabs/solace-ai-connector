"""Test the timer input component"""

import sys

sys.path.append("src")
import time
import pytest

from solace_ai_connector.test_utils.utils_for_test_files import (
    create_test_flows,
    create_connector,
    dispose_connector,
    # send_and_receive_message_on_flow,
    send_message_to_flow,
    get_message_from_flow,
)
from solace_ai_connector.common.message import Message
from solace_ai_connector.common.log import log


def test_basic_timer():
    """Test the timer input component without a catchup timer"""
    config_yaml = """
log:
  log_file_level: DEBUG
  log_file: solace_ai_connector.log
flows:
  - name: test_flow
    components:
      - component_name: timer_input
        component_module: timer_input
        component_config:
          interval_ms: 500
          skip_messages_if_behind: false
  - name: add_timestamp
    components:
      - component_name: add_timestamp
        component_module: pass_through
        input_transforms:
          - type: copy
            source_expression: 
              invoke:
                module: time
                function: time
            dest_expression: user_data.timestamp
        input_selection:
          source_expression: user_data.timestamp
"""

    start_time = time.time()
    connector, flows = create_test_flows(config_yaml)
    flow = flows[0]

    try:
        # Get the output messages (should be at least 3 seconds worth)
        for i in range(6):
            get_message_from_flow(flow)
            current_time = time.time()
            assert current_time - start_time >= i * 0.5

        end_time = time.time()
        duration = end_time - start_time
        assert duration > 2.5
        assert duration < 3.5
    finally:
        # Clean up
        dispose_connector(connector)


def test_with_no_skip_timer():
    """Create a simple timer input component with a catchup timer."""
    config_yaml = """
log:
  log_file_level: DEBUG
  log_file: solace_ai_connector.log
flows:
  - name: test_flow
    components:
      - component_name: timer_input
        component_module: timer_input
        component_config:
          interval_ms: 500
          skip_messages_if_behind: false
"""

    connector, flows = create_test_flows(config_yaml, queue_size=1)
    flow = flows[0]

    # Wait for 3 seconds - should get 6 messages quickly
    log.debug("waiting for 3 seconds")
    time.sleep(3)
    log.debug("done waiting")

    # Get the output messages
    start_time = time.time()

    try:
        for i in range(6):
            log.debug("getting message")
            get_message_from_flow(flow)
            log.debug("got message")
            current_time = time.time()
            assert current_time - start_time <= (i + 1) * 0.2

        end_time = time.time()
        duration = end_time - start_time
        assert duration < 0.5
    finally:
        # Clean up
        dispose_connector(connector)


def test_with_skip_timer():
    """Create a simple timer input component with a catchup timer."""
    config_yaml = """
log:
  log_file_level: DEBUG
  log_file: solace_ai_connector.log
flows:
  - name: test_flow
    components:
      - component_name: timer_input
        component_module: timer_input
        component_config:
          interval_ms: 500
          skip_messages_if_behind: true
"""

    connector, flows = create_test_flows(config_yaml, queue_size=1)
    flow = flows[0]

    # Wait for 3 seconds - now the missed messages should be skipped
    # There is one in our queue and another one blocked on putting into
    # the queue. Then the next ones should be spaced by 0.5 seconds each
    time.sleep(3)

    # Get the output messages
    start_time = time.time()

    # Grab the two available
    get_message_from_flow(flow)
    get_message_from_flow(flow)
    get_message_from_flow(flow)

    try:
        for i in range(6):
            log.debug("getting message")
            get_message_from_flow(flow)
            log.debug("got message")
            current_time = time.time()
            assert current_time - start_time >= i * 0.5

        end_time = time.time()
        duration = end_time - start_time
        assert duration > 2.5
        assert duration < 3.5
    finally:
        # Clean up
        dispose_connector(connector)
