"""Collection of functions to be used in test files"""

import queue
import sys
import os
import yaml

sys.path.insert(0, os.path.abspath("src"))


# from solace_ai_connector.common.message import Message
from solace_ai_connector.solace_ai_connector import (  # pylint: disable=wrong-import-position
    SolaceAiConnector,
)
from solace_ai_connector.common.log import (  # pylint: disable=wrong-import-position
    log,
)


class TestOutputComponent:
    """A simple output component that receives the output from the previous component.
    It is used to test the output of a flow."""

    def __init__(self, queue_timeout=None, queue_size=0):
        self.queue = queue.Queue(queue_size)
        self.queue_timeout = queue_timeout
        self.stop = False

    def enqueue(self, message):
        do_loop = True
        while do_loop and not self.stop:
            try:
                self.queue.put(message, timeout=1)
                do_loop = False
            except queue.Full:
                pass

    def stop_output(self):
        self.stop = True

    def get_output(self):
        try:
            message = self.queue.get(timeout=self.queue_timeout)
            log.debug("Output test component received message: %s", message)
        except queue.Empty:
            message = None
        return message


class TestInputComponent:
    """A simple input component that allows for the input of a message.
    It is used to test the input of a flow."""

    def __init__(self, next_component_queue):
        self.next_component_queue = next_component_queue

    def enqueue(self, message):
        log.debug("Input test component sending message: %s", message)
        self.next_component_queue.put(message)


def create_connector(config_yaml, event_handlers=None, error_queue=None):
    """Create a connector from a config"""

    # Create the connector
    connector = SolaceAiConnector(
        yaml.safe_load(config_yaml),
        event_handlers=event_handlers,
        error_queue=error_queue,
    )
    connector.run()

    # Return the connector
    return connector


def create_test_flows(config_yaml, queue_timeout=None, error_queue=None, queue_size=0):
    # Create the connector
    connector = create_connector(config_yaml, error_queue=error_queue)

    flows = connector.get_flows()

    # For each of the flows, add the input and output components
    flow_info = []
    for flow in flows:
        input_component = TestInputComponent(
            flow.component_groups[0][0].get_input_queue()
        )
        output_component = TestOutputComponent(
            queue_timeout=queue_timeout, queue_size=queue_size
        )
        for component in flow.component_groups[-1]:
            component.set_next_component(output_component)
        flow_info.append(
            {
                "flow": flow,
                "input_component": input_component,
                "output_component": output_component,
            }
        )

    return connector, flow_info


def stop_test_flows(connector):
    # For each of the flows, check if the last component is a TestOutputComponent
    # If so, stop its output
    for flow in connector.get_flows():
        last_component = flow.component_groups[-1][-1]
        # Get its next component
        next_component = last_component.get_next_component()
        if isinstance(next_component, TestOutputComponent):
            next_component.stop_output()


def send_message_to_flow(flow_info, message):
    input_component = flow_info["input_component"]
    input_component.enqueue(message)


def get_message_from_flow(flow_info):
    output_component = flow_info["output_component"]
    return output_component.get_output()


def dispose_connector(connector):
    stop_test_flows(connector)
    connector.stop()


def create_and_run_component(
    config_yaml, message, queue_timeout=None, error_queue=None, no_output=False
):
    connector, flow_info = create_test_flows(
        config_yaml, queue_timeout=queue_timeout, error_queue=error_queue
    )
    try:
        send_message_to_flow(flow_info[0], message)
        output_message = None
        if not no_output:
            output_message = get_message_from_flow(flow_info[0])
    except Exception as e:
        dispose_connector(connector)
        raise e
    dispose_connector(connector)
    return output_message


def send_and_receive_message_on_flow(flow, message):
    send_message_to_flow(flow, message)
    output_message = get_message_from_flow(flow)
    return output_message
