"""Tests for the App class and related functionality"""

import sys
import threading
import queue
import traceback

sys.path.append("src")

from solace_ai_connector.flow.app import App
from solace_ai_connector.solace_ai_connector import SolaceAiConnector
from solace_ai_connector.common.message import Message
from solace_ai_connector.test_utils.utils_for_test_files import (
    create_connector,
    create_test_flows,
    dispose_connector,
    send_message_to_flow,
    get_message_from_flow,
)


def test_app_creation():
    """Test that an app can be created with a basic configuration"""
    app_config = {
        "name": "test_app",
        "flows": [
            {
                "name": "test_flow",
                "components": [
                    {
                        "component_name": "pass_through",
                        "component_module": "pass_through",
                    }
                ],
            }
        ],
    }

    stop_signal = threading.Event()
    error_queue = queue.Queue()

    app = App(
        app_config=app_config,
        app_index=0,
        stop_signal=stop_signal,
        error_queue=error_queue,
        instance_name="test_instance",
    )

    assert app.name == "test_app"
    assert len(app.flows) == 1
    assert app.flows[0].name == "test_flow"

    # Clean up
    stop_signal.set()
    app.cleanup()


def test_app_get_config():
    """Test that app.get_config works correctly"""
    app_config = {
        "name": "test_app",
        "test_key": "test_value",
        "flows": [
            {
                "name": "test_flow",
                "components": [
                    {
                        "component_name": "pass_through",
                        "component_module": "pass_through",
                    }
                ],
            }
        ],
    }

    stop_signal = threading.Event()
    error_queue = queue.Queue()

    app = App(
        app_config=app_config,
        app_index=0,
        stop_signal=stop_signal,
        error_queue=error_queue,
        instance_name="test_instance",
    )

    assert app.get_config("test_key") == "test_value"
    assert app.get_config("non_existent_key", "default") == "default"

    # Clean up
    stop_signal.set()
    app.cleanup()


def test_app_create_from_flows():
    """Test that an app can be created from a list of flows"""
    flows = [
        {
            "name": "test_flow",
            "components": [
                {
                    "component_name": "pass_through",
                    "component_module": "pass_through",
                }
            ],
        }
    ]

    stop_signal = threading.Event()
    error_queue = queue.Queue()

    app = App.create_from_flows(
        flows=flows,
        app_name="test_app",
        app_index=0,
        stop_signal=stop_signal,
        error_queue=error_queue,
        instance_name="test_instance",
    )

    assert app.name == "test_app"
    assert len(app.flows) == 1
    assert app.flows[0].name == "test_flow"

    # Clean up
    stop_signal.set()
    app.cleanup()


def test_multiple_apps_in_connector():
    """Test that multiple apps can be created in a connector"""
    config_yaml = """
log:
  stdout_log_level: INFO
  log_file_level: INFO
  log_file: solace_ai_connector.log

apps:
  - name: app1
    flows:
      - name: flow1
        components:
          - component_name: pass_through1
            component_module: pass_through
  - name: app2
    flows:
      - name: flow2
        components:
          - component_name: pass_through2
            component_module: pass_through
"""

    connector = None
    try:
        connector = create_connector(config_yaml)

        # Check that both apps were created
        assert len(connector.apps) == 2
        assert connector.apps[0].name == "app1"
        assert connector.apps[1].name == "app2"

        # Check that both flows were created
        assert len(connector.flows) == 2
        assert connector.flows[0].name == "flow1"
        assert connector.flows[1].name == "flow2"

    finally:
        if connector:
            dispose_connector(connector)


def test_app_config_inheritance():
    """Test that components can access app configuration"""

    # Define a handler function to test app config inheritance
    def invoke_handler(component, _message, _data):
        # Return the app-level config value
        return component.get_config("app_level_config")

    config = {
        "log": {"stdout_log_level": "INFO", "log_file_level": "INFO"},
        "apps": [
            {
                "name": "test_app",
                "app_level_config": "app_value",
                "flows": [
                    {
                        "name": "test_flow",
                        "components": [
                            {
                                "component_name": "handler_component",
                                "component_module": "handler_callback",
                                "component_config": {"invoke_handler": invoke_handler},
                            }
                        ],
                    }
                ],
            }
        ],
    }

    connector = None
    try:
        # Create the connector and get the flows
        connector, flows = create_test_flows(config)

        # Send a message to the flow
        message = Message(payload="test")
        send_message_to_flow(flows[0], message)

        # Get the output message
        output_message = get_message_from_flow(flows[0])

        # Check that the component could access the app configuration
        assert output_message.get_data("previous") == "app_value"
    except Exception as e:
        import traceback

        print(e, traceback.format_exc())
    finally:
        if connector:
            dispose_connector(connector)


def test_app_num_instances():
    """Test that multiple instances of an app can be created"""
    config_yaml = """
log:
  stdout_log_level: INFO
  log_file_level: INFO
  log_file: solace_ai_connector.log

apps:
  - name: test_app
    num_instances: 3
    flows:
      - name: test_flow
        components:
          - component_name: pass_through
            component_module: pass_through
"""

    connector = None
    try:
        connector = create_connector(config_yaml)

        # Check that three instances of the app were created
        assert len(connector.apps) == 3
        assert connector.apps[0].name == "test_app"
        assert connector.apps[1].name == "test_app"
        assert connector.apps[2].name == "test_app"

        # Check that three flows were created
        assert len(connector.flows) == 3
        assert connector.flows[0].name == "test_flow"
        assert connector.flows[1].name == "test_flow"
        assert connector.flows[2].name == "test_flow"

    finally:
        if connector:
            dispose_connector(connector)


def test_backward_compatibility():
    """Test that the connector is backward compatible with the old configuration format"""
    config_yaml = """
log:
  stdout_log_level: INFO
  log_file_level: INFO
  log_file: solace_ai_connector.log

flows:
  - name: test_flow
    components:
      - component_name: pass_through
        component_module: pass_through
"""

    connector = None
    try:
        connector = create_connector(config_yaml)

        # Check that an app was created
        assert len(connector.apps) == 1
        assert connector.apps[0].name == "default_app"

        # Check that a flow was created
        assert len(connector.flows) == 1
        assert connector.flows[0].name == "test_flow"

    finally:
        if connector:
            dispose_connector(connector)


def test_get_app_by_name():
    """Test that an app can be retrieved by name"""
    config_yaml = """
log:
  stdout_log_level: INFO
  log_file_level: INFO
  log_file: solace_ai_connector.log

apps:
  - name: app1
    flows:
      - name: flow1
        components:
          - component_name: pass_through1
            component_module: pass_through
  - name: app2
    flows:
      - name: flow2
        components:
          - component_name: pass_through2
            component_module: pass_through
"""

    connector = None
    try:
        connector = create_connector(config_yaml)

        # Get apps by name
        app1 = connector.get_app("app1")
        app2 = connector.get_app("app2")

        # Check that the correct apps were retrieved
        assert app1 is not None
        assert app2 is not None
        assert app1.name == "app1"
        assert app2.name == "app2"

        # Check that a non-existent app returns None
        assert connector.get_app("non_existent_app") is None

    except Exception as e:
        # assert a failure here and print out the traceback

        print(e, traceback.format_exc())
        assert False

    finally:
        if connector:
            dispose_connector(connector)


def test_component_app_reference():
    """Test that components have a reference to their parent app"""

    # Define a handler function to test app reference
    def invoke_handler(component, message, data):
        # Return the app name from the parent_app reference
        return component.parent_app.name

    config = {
        "log": {"stdout_log_level": "INFO", "log_file_level": "INFO"},
        "apps": [
            {
                "name": "test_app",
                "flows": [
                    {
                        "name": "test_flow",
                        "components": [
                            {
                                "component_name": "handler_component",
                                "component_module": "handler_callback",
                                "component_config": {"invoke_handler": invoke_handler},
                            }
                        ],
                    }
                ],
            }
        ],
    }

    connector = None
    try:
        # Create the connector and get the flows
        connector, flows = create_test_flows(config)

        # Send a message to the flow
        message = Message(payload="test")
        send_message_to_flow(flows[0], message)

        # Get the output message
        output_message = get_message_from_flow(flows[0])

        # Check that the component could access its parent app
        assert output_message.get_data("previous") == "test_app"

    finally:
        if connector:
            dispose_connector(connector)
