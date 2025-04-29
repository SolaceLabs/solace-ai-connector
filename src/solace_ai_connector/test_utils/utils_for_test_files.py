import os
import queue
import sys
import yaml

sys.path.insert(0, os.path.abspath("src"))

from solace_ai_connector.solace_ai_connector import SolaceAiConnector
from solace_ai_connector.common.log import log
from solace_ai_connector.common.event import Event, EventType
from solace_ai_connector.common.message import Message

# from solace_ai_connector.common.message import Message


class TestOutputComponent:
    """A simple output component that receives the output from the previous component.
    It is used to test the output of a flow."""

    def __init__(self, queue_timeout=None, queue_size=0):
        self.queue = queue.Queue(queue_size)
        self.queue_timeout = queue_timeout
        self.stop = False

    def enqueue(self, event):
        do_loop = True
        while do_loop and not self.stop:
            try:
                self.queue.put(event, timeout=1)
                do_loop = False
            except queue.Full:
                pass

    def stop_output(self):
        self.stop = True

    def get_output(self):
        try:
            item = self.queue.get(timeout=self.queue_timeout)
            log.debug("Output test component received item.")
            return item
        except queue.Empty:
            pass
        return None


class TestInputComponent:
    """A simple input component that allows for the input of an event.
    It is used to test the input of a flow."""

    def __init__(self, next_component_queue):
        self.next_component_queue = next_component_queue

    def enqueue(self, message):
        log.debug("Input test component sending message.")
        if not isinstance(message, Event):
            event = Event(EventType.MESSAGE, message)
        else:
            event = message
        self.next_component_queue.put(event)


def create_connector(config_or_yaml, event_handlers=None, error_queue=None):
    """Create a connector from a config that can be an object or a yaml string"""

    config = config_or_yaml
    if isinstance(config_or_yaml, str):
        config = yaml.safe_load(config_or_yaml)

    # Create the connector
    connector = SolaceAiConnector(
        config,
        event_handlers=event_handlers,
        error_queue=error_queue,
    )
    connector.run()

    # Return the connector
    return connector


def run_component_test(
    module_or_name,
    validation_func,
    component_config=None,
    input_data=None,
    input_messages=None,
    input_selection=None,
    input_transforms=None,
    max_response_timeout=None,
):
    if not input_data and not input_messages:
        raise ValueError("Either input_data or input_messages must be provided")

    if input_data and input_messages:
        raise ValueError("Only one of input_data or input_messages can be provided")

    if input_data and not isinstance(input_data, list):
        input_data = [input_data]

    if input_messages and not isinstance(input_messages, list):
        input_messages = [input_messages]

    if not input_messages:
        input_messages = []

    if input_selection:
        if isinstance(input_selection, str):
            input_selection = {"source_expression": input_selection}

    connector = None
    try:
        connector, flows = create_test_flows(
            {
                "flows": [
                    {
                        "name": "test_flow",
                        "components": [
                            {
                                "component_name": "test_component",
                                "component_module": module_or_name,
                                "component_config": component_config or {},
                                "input_selection": input_selection,
                                "input_transforms": input_transforms,
                            }
                        ],
                    }
                ]
            },
            queue_timeout=max_response_timeout,
        )

        if input_data:
            for data in input_data:
                message = Message(payload=data)
                message.set_previous(data)
                input_messages.append(message)

        # Send each message through, one at a time
        output_data_list = []
        output_message_list = []
        for message in input_messages:
            send_message_to_flow(flows[0], message)
            output_message = get_message_from_flow(flows[0])
            if not output_message:
                # This only happens if the max_response_timeout is reached
                output_message_list.append(None)
                output_data_list.append(None)
                continue
            output_data_list.append(output_message.get_data("previous"))
            output_message_list.append(output_message)

        validation_func(output_data_list, output_message_list, message)

    finally:
        if connector:
            dispose_connector(connector)


def create_test_flows(
    config_or_yaml, queue_timeout=None, error_queue=None, queue_size=0
):
    # Create the connector
    connector = create_connector(config_or_yaml, error_queue=error_queue)

    flows = connector.get_flows()

    # For each of the flows, add the input and output components
    flow_info = []
    for flow in flows:
        if flow.flow_config.get("test_ignore", False):
            continue
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
    event = output_component.get_output()
    if not event:
        return event
    if event.event_type != EventType.MESSAGE:
        raise ValueError("Expected a message event")
    return event.data


def get_event_from_flow(flow_info):
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
    except Exception:
        dispose_connector(connector)
        raise ValueError("Failed to create and run component.")
    dispose_connector(connector)
    return output_message


def send_and_receive_message_on_flow(flow, message):
    send_message_to_flow(flow, message)
    output_message = get_message_from_flow(flow)
    return output_message
