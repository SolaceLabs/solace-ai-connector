"""Test various things related to the configuration file"""

import sys
import yaml
import pytest

sys.path.append("src")

from utils_for_test_files import (  # pylint: disable=wrong-import-position
    create_connector,
)

from solace_ai_connector.solace_ai_connector import (  # pylint: disable=wrong-import-position
    SolaceAiConnector,
)

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
        assert str(e) == "No flows defined in configuration file"


def test_no_flow_name():
    """Test that the program exits if no flow name is provided"""
    try:
        config_yaml = """
log:
  log_file_level: DEBUG
  log_file: solace_ai_connector.log
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
        assert str(e) == "Flow name not provided in flow 0"


def test_no_flow_components():
    """Test that the program exits if no flow components list is provided"""
    try:
        config_yaml = """
log:
  log_file_level: DEBUG
  log_file: solace_ai_connector.log
flows:
  - name: test_flow
"""
        SolaceAiConnector(
            yaml.safe_load(config_yaml),
        )
    except ValueError as e:
        assert str(e) == "Flow components list not provided in flow 0"


def test_flow_components_not_list():
    """Test that the program exits if the flow components list is not a list"""
    try:
        config_yaml = """
log:
  log_file_level: DEBUG
  log_file: solace_ai_connector.log
flows:
  - name: test_flow
    components: not_a_list
"""
        SolaceAiConnector(
            yaml.safe_load(config_yaml),
        )
    except ValueError as e:
        assert str(e) == "Flow components is not a list in flow 0"


def test_no_component_name():
    """Test that the program exits if no component name is provided"""
    try:
        config_yaml = """
log:
  log_file_level: DEBUG
  log_file: solace_ai_connector.log
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
        assert str(e) == "component_name not provided in flow 0, component 0"


def test_no_component_module():
    """Test that the program exits if no component module is provided"""
    try:
        config_yaml = """
log:
  log_file_level: DEBUG
  log_file: solace_ai_connector.log 
flows:
  - name: test_flow
    components:
      - component_name: delay1
"""
        SolaceAiConnector(
            yaml.safe_load(config_yaml),
        )
    except ValueError as e:
        assert str(e) == "component_module not provided in flow 0, component 0"


def test_bad_module():
    """Test that the program exits if the component module is not found"""
    try:
        config_yaml = """
log:
  log_file_level: DEBUG
  log_file: solace_ai_connector.log
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
        assert str(e) == "Module 'not_a_module' not found"
    finally:
        print("Finally")


def test_component_missing_info_attribute():
    """Test that the program exits if the component module is missing the info attribute"""
    config_yaml = """
log:
  log_file_level: DEBUG
  log_file: solace_ai_connector.log
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
    assert (
        str(e.value)
        == "Component module 'utils' does not have an 'info' attribute. It probably isn't a valid component."
    )
