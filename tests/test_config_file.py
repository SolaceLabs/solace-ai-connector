"""Test various things related to the configuration file"""

import sys
import pytest
import yaml

sys.path.append("src")

from solace_ai_connector.test_utils.utils_for_test_files import (  # pylint: disable=wrong-import-position
    create_connector,
    create_test_flows,
    dispose_connector,
    send_message_to_flow,
    get_message_from_flow,
)

from solace_ai_connector.solace_ai_connector import (  # pylint: disable=wrong-import-position
    SolaceAiConnector,
)

from solace_ai_connector.common.message import Message
import solace_ai_connector.components.general.pass_through

# from solace_ai_connector.common.log import log


def test_no_config_file():
    """Test that the program exits if no configuration file is provided"""
    try:
        SolaceAiConnector(None)
    except ValueError as e:
        assert str(e) == "No config provided"


def test_no_flows():
    """Test that the program exits if no flows are defined in the configuration file"""
    try:
        config_yaml = """
log:
  log_file_level: DEBUG
  log_file: solace_ai_connector.log
"""
        SolaceAiConnector(
            yaml.safe_load(config_yaml),
        )
    except ValueError as e:
        assert str(e) == "No apps or flows defined in configuration file"


def test_no_flow_name():
    """Test that the program exits if no flow name is provided"""
    try:
        config_yaml = """
log:
  log_file_level: DEBUG
  log_file: solace_ai_connector.log
apps:
  - name: test_app
    flows:
      - components:
          - component_name: delay1
            component_module: delay
            component_config:
              delay: 0.1
            num_instances: 4
            input_transforms:
              - type: append
                source_expression: self:component_index
                dest_expression: user_data.path:my_path
            input_selection:
              source_expression: input.payload:text
"""
        SolaceAiConnector(
            yaml.safe_load(config_yaml),
        )
    except ValueError as e:
        assert str(e) == "Flow name not provided in flow 0 of app test_app"


def test_no_flow_components():
    """Test that the program exits if no flow components list is provided"""
    try:
        config_yaml = """
log:
  log_file_level: DEBUG
  log_file: solace_ai_connector.log
apps:
  - name: test_app
    flows:
      - name: test_flow
"""
        SolaceAiConnector(
            yaml.safe_load(config_yaml),
        )
    except ValueError as e:
        assert str(e) == "Flow components list not provided in flow 0 of app test_app"


def test_flow_components_not_list():
    """Test that the program exits if the flow components list is not a list"""
    try:
        config_yaml = """
log:
  log_file_level: DEBUG
  log_file: solace_ai_connector.log
apps:
  - name: test_app
    flows:
      - name: test_flow
        components: not_a_list
"""
        SolaceAiConnector(
            yaml.safe_load(config_yaml),
        )
    except ValueError as e:
        assert str(e) == "Flow components is not a list in flow 0 of app test_app"


def test_no_component_name():
    """Test that the program exits if no component name is provided"""
    try:
        config_yaml = """
log:
  log_file_level: DEBUG
  log_file: solace_ai_connector.log
apps:
  - name: test_app
    flows:
      - name: test_flow
        components:
          - component_module: delay
            input_selection:
              source_expression: input.payload:text
"""
        SolaceAiConnector(
            yaml.safe_load(config_yaml),
        )
    except ValueError as e:
        assert (
            str(e)
            == "component_name not provided in flow 0, component 0 of app test_app"
        )


def test_no_component_module():
    """Test that the program exits if no component module is provided"""
    try:
        config_yaml = """
log:
  log_file_level: DEBUG
  log_file: solace_ai_connector.log 
apps:
  - name: test_app
    flows:
      - name: test_flow
        components:
          - component_name: delay1
"""
        SolaceAiConnector(
            yaml.safe_load(config_yaml),
        )
    except ValueError as e:
        assert (
            str(e)
            == "component_module not provided in flow 0, component 0 of app test_app"
        )


def test_static_import_and_object_config():
    """Test that we can statically import a module and pass an object for the config"""

    config = {
        "log": {"log_file_level": "DEBUG", "log_file": "solace_ai_connector.log"},
        "apps": [
            {
                "name": "test_app",
                "flows": [
                    {
                        "name": "test_flow",
                        "components": [
                            {
                                "component_name": "delay1",
                                "component_module": solace_ai_connector.components.general.pass_through,
                                "component_config": {"delay": 0.1},
                                "input_selection": {
                                    "source_expression": "input.payload"
                                },
                            }
                        ],
                    }
                ],
            }
        ],
    }
    connector = None
    try:
        connector, flows = create_test_flows(config)

        # Test pushing a simple message through the delay component
        message = Message(payload={"text": "Hello, World!"})
        send_message_to_flow(flows[0], message)

        # Get the output message
        output_message = get_message_from_flow(flows[0])

        # Check that the output is correct
        assert output_message.get_data("previous") == {"text": "Hello, World!"}

    except Exception as e:
        pytest.fail(f"Test failed with exception: {e}")
    finally:
        if "connector" in locals():
            dispose_connector(connector)


def test_bad_module():
    """Test that the program exits if the component module is not found"""
    try:
        config_yaml = """
log:
  log_file_level: DEBUG
  log_file: solace_ai_connector.log
apps:
  - name: test_app
    flows:
      - name: test_flow
        components:
          - component_name: delay1
            component_module: not_a_module
"""
        sac = SolaceAiConnector(
            yaml.safe_load(config_yaml),
        )
        sac.run()
    except Exception as e:
        assert str(e) == "An error occurred during startup"
    finally:
        print("Finally")


def test_component_missing_info_attribute():
    """Test that the program exits if the component module is missing the info attribute"""
    config_yaml = """
log:
  log_file_level: DEBUG
  log_file: solace_ai_connector.log
apps:
  - name: test_app
    flows:
      - name: test_flow
        components:
          - component_name: delay1
            component_module: utils
"""
    with pytest.raises(ValueError) as e:
        create_connector(
            config_yaml,
        )
    assert str(e.value) == "An error occurred during startup"
