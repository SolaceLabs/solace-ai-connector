import pytest
import sys
from unittest.mock import MagicMock

# Ensure src directory is in path for imports
sys.path.append("src")

from solace_ai_connector.flow.app import App

# --- Test Fixtures and Helper Classes ---


# Define a custom App subclass WITH a schema for testing validation
class ValidatedApp(App):
    app_schema = {
        "config_parameters": [
            {
                "name": "required_param",
                "required": True,
                "type": "string",
                "description": "A required string parameter.",
            },
            {
                "name": "optional_param",
                "required": False,
                "type": "integer",
                "default": 100,
                "description": "An optional integer parameter with a default.",
            },
            {
                "name": "param_no_default",
                "required": False,
                "type": "boolean",
                "description": "An optional boolean parameter without a default.",
            },
        ]
    }

    # Override _initialize_flows to prevent actual flow/component creation during validation tests
    def _initialize_flows(self):
        self.flows = []
        self.flow_input_queues = {}


# Define a custom App subclass WITHOUT a schema
class UnvalidatedApp(App):
    # No app_schema defined

    # Override _initialize_flows to prevent actual flow/component creation
    def _initialize_flows(self):
        self.flows = []
        self.flow_input_queues = {}


@pytest.fixture
def mock_dependencies():
    """Provides common mock dependencies for App initialization."""
    return {
        "app_index": 0,
        "stop_signal": MagicMock(),
        "error_queue": MagicMock(),
        "instance_name": "test_instance",
        "trace_queue": None,
        "connector": MagicMock(),
    }


# --- Test Cases ---


def test_app_validation_success(mock_dependencies):
    """Tests successful validation when all required params are present."""
    app_info = {
        "name": "test_success_app",
        "app_config": {
            "required_param": "value_provided",
            "optional_param": 50,  # Override default
            "param_no_default": True,
        },
        # Minimal structure for App init
        "flows": [],
    }
    app = ValidatedApp(app_info=app_info, **mock_dependencies)
    assert app.app_config["required_param"] == "value_provided"
    assert app.app_config["optional_param"] == 50
    assert app.app_config["param_no_default"] is True


def test_app_validation_default_applied(mock_dependencies):
    """Tests that default values are applied correctly."""
    app_info = {
        "name": "test_default_app",
        "app_config": {
            "required_param": "another_value",
            # optional_param is missing, should get default
            # param_no_default is missing, should remain missing
        },
        "flows": [],
    }
    app = ValidatedApp(app_info=app_info, **mock_dependencies)
    assert app.app_config["required_param"] == "another_value"
    assert app.app_config["optional_param"] == 100  # Default value applied
    assert "param_no_default" not in app.app_config  # Remains absent


def test_app_validation_missing_required_raises_error(mock_dependencies):
    """Tests that ValueError is raised when a required parameter is missing."""
    app_info = {
        "name": "test_missing_required_app",
        "app_config": {
            # required_param is missing
            "optional_param": 200,
        },
        "flows": [],
    }
    with pytest.raises(ValueError) as excinfo:
        ValidatedApp(app_info=app_info, **mock_dependencies)
    assert "Required configuration parameter 'required_param' is missing" in str(
        excinfo.value
    )
    assert "App 'test_missing_required_app'" in str(excinfo.value)


def test_app_validation_empty_config(mock_dependencies):
    """Tests validation failure when app_config is empty but params are required."""
    app_info = {
        "name": "test_empty_config_app",
        "app_config": {},  # Empty config
        "flows": [],
    }
    with pytest.raises(ValueError) as excinfo:
        ValidatedApp(app_info=app_info, **mock_dependencies)
    assert "Required configuration parameter 'required_param' is missing" in str(
        excinfo.value
    )


def test_app_validation_no_app_config_block(mock_dependencies):
    """Tests validation failure when the app_config block itself is missing."""
    app_info = {
        "name": "test_no_block_app",
        # app_config block is missing entirely
        "flows": [],
    }
    # The app_config instance attribute will be {} in this case
    with pytest.raises(ValueError) as excinfo:
        ValidatedApp(app_info=app_info, **mock_dependencies)
    assert "Required configuration parameter 'required_param' is missing" in str(
        excinfo.value
    )


def test_unvalidated_app_no_error(mock_dependencies):
    """Tests that an App without a schema doesn't raise errors for arbitrary config."""
    app_info = {
        "name": "test_unvalidated_app",
        "app_config": {
            "arbitrary_param": "some_value",
            "another_one": 123,
            # required_param from ValidatedApp schema is not here, but it shouldn't matter
        },
        "flows": [],
    }
    try:
        app = UnvalidatedApp(app_info=app_info, **mock_dependencies)
        # Check that the config was stored correctly
        assert app.app_config["arbitrary_param"] == "some_value"
        assert app.app_config["another_one"] == 123
    except ValueError:
        pytest.fail(
            "UnvalidatedApp raised ValueError unexpectedly during initialization."
        )


def test_base_app_no_error(mock_dependencies):
    """Tests that the base App class doesn't raise errors for arbitrary config."""
    app_info = {
        "name": "test_base_app",
        "app_config": {
            "base_app_param": True,
            "whatever": "data",
        },
        "flows": [],  # Need flows for standard app structure
    }
    try:
        app = App(app_info=app_info, **mock_dependencies)
        # Check that the config was stored correctly
        assert app.app_config["base_app_param"] is True
        assert app.app_config["whatever"] == "data"
    except ValueError:
        pytest.fail(
            "Base App class raised ValueError unexpectedly during initialization."
        )
