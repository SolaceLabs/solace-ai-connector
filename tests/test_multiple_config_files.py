"""Tests for handling multiple configuration files"""

import sys
import os
import tempfile
import traceback

sys.path.append("src")

from solace_ai_connector.main import load_config, merge_config
from solace_ai_connector.solace_ai_connector import SolaceAiConnector
from solace_ai_connector.test_utils.utils_for_test_files import (
    create_connector,
    dispose_connector,
)


def test_load_config_with_app_creation():
    """Test that load_config creates an app from flows"""
    with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w+", delete=False) as f:
        f.write(
            """
log:
  stdout_log_level: INFO
flows:
  - name: test_flow
    components:
      - component_name: pass_through
        component_module: pass_through
"""
        )
        f.flush()
        filename = f.name

    try:
        # Load the config
        config = load_config(filename)

        # Check that an app was created with the filename as the name
        assert "apps" in config
        assert len(config["apps"]) == 1
        assert (
            config["apps"][0]["name"] == os.path.splitext(os.path.basename(filename))[0]
        )
        assert "flows" in config["apps"][0]
        assert len(config["apps"][0]["flows"]) == 1
        assert config["apps"][0]["flows"][0]["name"] == "test_flow"

        # Check that the original flows key was removed
        assert "flows" not in config
    finally:
        os.unlink(filename)


def test_merge_config_with_apps():
    """Test that merge_config correctly merges apps from multiple configs"""
    config1 = {
        "log": {"stdout_log_level": "INFO"},
        "apps": [{"name": "app1", "flows": [{"name": "flow1"}]}],
    }

    config2 = {
        "log": {"stdout_log_level": "DEBUG"},
        "apps": [{"name": "app2", "flows": [{"name": "flow2"}]}],
    }

    # Merge the configs
    merged = merge_config(config1, config2)

    # Check that the apps were merged correctly
    assert "apps" in merged
    assert len(merged["apps"]) == 2
    assert merged["apps"][0]["name"] == "app1"
    assert merged["apps"][1]["name"] == "app2"

    # Check that other keys were overwritten
    assert merged["log"]["stdout_log_level"] == "DEBUG"


def test_multiple_config_files_integration():
    """Integration test for handling multiple configuration files"""
    # Create two temporary config files
    with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w+", delete=False) as f1:
        f1.write(
            """
log:
  stdout_log_level: INFO
  log_file_level: INFO
  log_file: solace_ai_connector.log

flows:
  - name: flow1
    components:
      - component_name: pass_through1
        component_module: pass_through
"""
        )
        f1.flush()
        filename1 = f1.name

    with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w+", delete=False) as f2:
        f2.write(
            """
flows:
  - name: flow2
    components:
      - component_name: pass_through2
        component_module: pass_through
"""
        )
        f2.flush()
        filename2 = f2.name

    try:
        # Load and merge the configs
        config1 = load_config(filename1)
        config2 = load_config(filename2)
        merged_config = merge_config(config1, config2)

        # Create a connector with the merged config
        connector = SolaceAiConnector(
            merged_config, config_filenames=[filename1, filename2]
        )
        
        # Run the connector to create the apps
        connector.run()

        # Check that two apps were created, one for each file
        assert len(connector.apps) == 2
        app_names = [app.name for app in connector.apps]
        assert os.path.splitext(os.path.basename(filename1))[0] in app_names
        assert os.path.splitext(os.path.basename(filename2))[0] in app_names

        # Check that two flows were created
        assert len(connector.flows) == 2
        flow_names = [flow.name for flow in connector.flows]
        assert "flow1" in flow_names
        assert "flow2" in flow_names

        # Clean up
        connector.stop()
        connector.cleanup()
    except Exception as e:
        print(e, traceback.format_exc())
        assert False, f"Exception: {e}"
    finally:
        os.unlink(filename1)
        os.unlink(filename2)


def test_component_config_inheritance():
    """Test that component configuration is inherited from app configuration"""
    # Define a handler function to test app config inheritance
    def invoke_handler(component, _message, _data):
        # Return the app-level config value
        return component.get_config("shared_config_value")
    
    # Create a config file with app-level configuration
    with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w+", delete=False) as f:
        f.write(
            """
log:
  stdout_log_level: INFO
  log_file_level: INFO
  log_file: solace_ai_connector.log

apps:
  - name: test_app
    shared_config_value: app_level_value
    flows:
      - name: test_flow
        components:
          - component_name: handler_component
            component_module: handler_callback
            component_config:
              invoke_handler: null
"""
        )
        f.flush()
        filename = f.name

    try:
        # Create a connector with the config
        connector = None
        try:
            config = load_config(filename)
            
            # Set the invoke_handler function
            config["apps"][0]["flows"][0]["components"][0]["component_config"]["invoke_handler"] = invoke_handler
            
            connector = SolaceAiConnector(config)
            connector.run()

            # Get the component
            component = connector.flows[0].component_groups[0][0]

            # Check that the component can access the app-level configuration
            assert component.get_config("shared_config_value") == "app_level_value"

        finally:
            if connector:
                connector.stop()
                connector.cleanup()
    finally:
        os.unlink(filename)
