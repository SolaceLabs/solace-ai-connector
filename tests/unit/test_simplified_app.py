import pytest
import re
import threading
import sys  # Add sys import

sys.path.append("src")  # Add src directory to Python path
from unittest.mock import MagicMock, patch, ANY  # Import patch

# Imports for classes to test/mock
from solace_ai_connector.flow.app import App
from solace_ai_connector.flow.flow import Flow
from solace_ai_connector.components.component_base import ComponentBase
from solace_ai_connector.flow.subscription_router import SubscriptionRouter
from solace_ai_connector.common.message import Message
from solace_ai_connector.common.event import Event, EventType
from solace_ai_connector.common.utils import deep_merge  # Import deep_merge

# --- Test Data and Mocks ---


# Dummy Component Class for testing component_class instantiation
class DummyComponent(ComponentBase):
    # Define info as a class attribute
    info = {"class_name": "DummyComponent", "config_parameters": []}

    def __init__(self, **kwargs):
        # Pass the class attribute info to the base class
        super().__init__(self.info, **kwargs)  # Use self.info or DummyComponent.info

    def invoke(self, message, data):
        return data  # Simple pass-through


# Dummy App Subclass for testing config merging
class DummyAppWithCodeConfig(App):
    app_config = {
        "name": "app_from_code",
        "broker": {
            "broker_type": "code_broker",
            "broker_url": "code_url",
            "input_enabled": False,  # Code default
        },
        # Use 'app_config' key here for app-level parameters
        "app_config": {
            "code_param": "code_value",
            "shared_param": "code_shared",
        },
        "components": [{"name": "code_comp", "component_module": "code_module"}],
    }

    # Override _initialize_flows to prevent actual flow/component creation during init test
    # This focuses the test on the config merging part of App.__init__
    def _initialize_flows(self):
        print("Skipping flow initialization for merging test.")
        self.flows = [] # Ensure flows list exists but is empty
        self.flow_input_queues = {} # Ensure queues dict exists


# --- Test Cases ---


# 5.2.1 Test App.__init__ merging
def test_app_init_merging():
    """Tests deep merging of code config and YAML config in App.__init__."""
    yaml_config = {
        "name": "app_from_yaml",  # YAML name overrides code name
        "broker": {
            "broker_url": "yaml_url",  # YAML overrides code
            "broker_vpn": "yaml_vpn",  # YAML adds new key
            "input_enabled": True,  # YAML overrides code
        },
        # Use 'app_config' key here for app-level parameters
        "app_config": {
            "yaml_param": "yaml_value",  # YAML adds new key
            "shared_param": "yaml_shared",  # YAML overrides code
        },
        "components": [
            {
                "name": "yaml_comp",
                "component_module": "yaml_module",
            }  # YAML extends code list
        ],
        # No 'flows' key, indicating simplified app potentially
    }

    mock_stop_signal = MagicMock()
    mock_connector = MagicMock()

    # Instantiate the dummy app with YAML-like config
    app_instance = DummyAppWithCodeConfig(
        app_info=yaml_config,
        app_index=0,
        stop_signal=mock_stop_signal,
        connector=mock_connector,
    )

    # Assertions for self.app_info (merged result)
    assert app_instance.app_info["name"] == "app_from_yaml"
    assert (
        app_instance.app_info["broker"]["broker_type"] == "code_broker"
    )  # From code (not in YAML)
    assert app_instance.app_info["broker"]["broker_url"] == "yaml_url"  # From YAML
    assert app_instance.app_info["broker"]["broker_vpn"] == "yaml_vpn"  # From YAML
    assert app_instance.app_info["broker"]["input_enabled"] is True  # From YAML

    # Assertions for self.app_config (extracted 'app_config' block from merged result)
    assert (
        app_instance.app_config["code_param"] == "code_value"
    )  # From code (not in YAML app_config block)
    assert app_instance.app_config["yaml_param"] == "yaml_value"  # From YAML
    assert app_instance.app_config["shared_param"] == "yaml_shared"  # From YAML

    # Assertion for self.name (derived from merged result)
    assert app_instance.name == "app_from_yaml"

    # Assertion for components (YAML should extend the code list)
    assert len(app_instance.app_info["components"]) == 2
    # Check contents and order
    assert app_instance.app_info["components"][0]["name"] == "code_comp"
    assert app_instance.app_info["components"][0]["component_module"] == "code_module"
    assert app_instance.app_info["components"][1]["name"] == "yaml_comp"
    assert app_instance.app_info["components"][1]["component_module"] == "yaml_module"


# 5.2.2 Test App._create_simplified_flow_config
@pytest.mark.parametrize(
    "app_config_override, expected_components",
    [
        # Scenario 1: Input enabled, 1 component
        (
            {
                "broker": {"input_enabled": True, "output_enabled": False},
                "components": [{"name": "comp1", "subscriptions": [{"topic": "t1"}]}],
            },
            ["_broker_input", "comp1"],  # Expected component names/types
        ),
        # Scenario 2: Input enabled, 2 components (router needed)
        (
            {
                "broker": {"input_enabled": True, "output_enabled": False},
                "components": [
                    {"name": "comp1", "subscriptions": [{"topic": "t1"}]},
                    {"name": "comp2", "subscriptions": [{"topic": "t2"}]},
                ],
            },
            ["_broker_input", "_router", "comp1", "comp2"],
        ),
        # Scenario 3: Output enabled, 1 component
        (
            {
                "broker": {"input_enabled": False, "output_enabled": True},
                "components": [{"name": "comp1"}],  # No subscriptions needed
            },
            ["comp1", "_broker_output"],
        ),
        # Scenario 4: Input and Output enabled, 2 components
        (
            {
                "broker": {"input_enabled": True, "output_enabled": True},
                "components": [
                    {"name": "comp1", "subscriptions": [{"topic": "t1"}]},
                    {"name": "comp2", "subscriptions": [{"topic": "t2"}]},
                ],
            },
            ["_broker_input", "_router", "comp1", "comp2", "_broker_output"],
        ),
        # Scenario 5: Input enabled, 1 component, no subscriptions (warning expected)
        (
            {
                "broker": {"input_enabled": True, "output_enabled": False},
                "components": [{"name": "comp1"}],
            },
            ["_broker_input", "comp1"],
        ),
    ],
)
def test_create_simplified_flow_config(app_config_override, expected_components):
    """Tests the generation of the implicit flow config dictionary."""
    base_app_info = {
        "name": "test_simplified_app",
        "broker": {
            "broker_type": "solace",
            "broker_url": "url",
            "broker_username": "user",
            "broker_password": "pw",
            "broker_vpn": "vpn",
            "queue_name": "q/test",
            # Flags overridden by parametrize
        },
        "components": [],  # Overridden by parametrize
    }
    # Deep merge the override into the base using the imported function
    merged_app_info = deep_merge(base_app_info, app_config_override)

    # Mock App instance
    mock_app = MagicMock(spec=App)
    mock_app.app_info = merged_app_info
    mock_app.name = merged_app_info["name"]
    # Bind the method to the mock instance for testing
    mock_app._create_simplified_flow_config = (
        App._create_simplified_flow_config.__get__(mock_app, App)
    )

    # Call the method under test
    flow_config = mock_app._create_simplified_flow_config()

    # Assertions
    assert isinstance(flow_config, dict)
    assert flow_config["name"] == f"{mock_app.name}_implicit_flow"
    assert "components" in flow_config
    assert isinstance(flow_config["components"], list)

    generated_component_names = [
        c.get("component_name", c.get("name")) for c in flow_config["components"]
    ]

    # Check presence and order of implicit/user components
    assert len(generated_component_names) == len(expected_components)

    for i, expected in enumerate(expected_components):
        generated_name = generated_component_names[i]
        if expected == "_broker_input":
            assert generated_name.endswith("_broker_input")
            assert flow_config["components"][i]["component_module"] == "broker_input"
            # Check subscriptions passed to broker_input
            all_subs = [
                sub
                for comp in merged_app_info["components"]
                for sub in comp.get("subscriptions", [])
            ]
            assert (
                flow_config["components"][i]["component_config"]["broker_subscriptions"]
                == all_subs
            )
        elif expected == "_router":
            assert generated_name.endswith("_router")
            assert (
                flow_config["components"][i]["component_module"]
                == "subscription_router"
            )
            # Check reference passed to router
            assert (
                flow_config["components"][i]["component_config"][
                    "app_components_config_ref"
                ]
                == merged_app_info["components"]
            )
        elif expected == "_broker_output":
            assert generated_name.endswith("_broker_output")
            assert flow_config["components"][i]["component_module"] == "broker_output"
        else:
            # User component - check if name matches
            assert generated_name == expected


# 5.2.3 Test Flow.create_component_group with component_class
def test_flow_create_component_group_with_class():
    """Tests that Flow.create_component_group correctly uses component_class."""
    mock_flow = MagicMock(spec=Flow)
    mock_flow.flow_lock_manager = MagicMock()
    mock_flow.flow_kv_store = MagicMock()
    mock_flow.stop_signal = MagicMock()
    mock_flow.error_queue = MagicMock()
    mock_flow.trace_queue = None
    mock_flow.connector = MagicMock()
    mock_flow.connector.timer_manager = MagicMock()
    mock_flow.connector.cache_service = MagicMock()
    mock_flow.cache_service = MagicMock()  # Add missing cache_service attribute
    mock_flow.app = MagicMock()
    mock_flow.name = "test_flow"
    mock_flow.instance_name = "test_instance"
    mock_flow.put_errors_in_error_queue = True
    mock_flow.component_groups = []  # Initialize component_groups

    # Bind the method to the mock instance
    mock_flow.create_component_group = Flow.create_component_group.__get__(
        mock_flow, Flow
    )

    component_config = {
        "component_name": "dummy_instance",
        "component_class": DummyComponent,  # Pass the class directly
        "num_instances": 1,
        "component_config": {"dummy_param": "value"},
    }

    # Mock import_module to avoid actual imports for dependencies of DummyComponent if any were needed
    # Also mock the 'info' lookup if it relies on module import
    # Use DummyComponent.info now that it's a class attribute
    with patch(
        "solace_ai_connector.flow.flow.import_module",
        return_value=MagicMock(info=DummyComponent.info),
    ):
        mock_flow.create_component_group(component_config, 0)

    # Assertions
    assert len(mock_flow.component_groups) == 1
    assert len(mock_flow.component_groups[0]) == 1
    created_component = mock_flow.component_groups[0][0]
    assert isinstance(created_component, DummyComponent)
    assert created_component.name == "dummy_instance"
    # Check if component_config was passed down
    assert created_component.component_config.get("dummy_param") == "value"


# 5.2.4 Test SubscriptionRouter routing
@pytest.fixture
def mock_router_dependencies():
    """Provides mock App, Flow, and Components for SubscriptionRouter tests."""
    mock_app = MagicMock(spec=App)
    mock_flow = MagicMock(spec=Flow)
    mock_comp_a = MagicMock(spec=ComponentBase)
    mock_comp_a.name = "comp_a"
    mock_comp_a.enqueue = MagicMock()
    mock_comp_b = MagicMock(spec=ComponentBase)
    mock_comp_b.name = "comp_b"
    mock_comp_b.enqueue = MagicMock()

    mock_app.flows = [mock_flow]  # Simplified app has one flow
    # Simulate component groups after BrokerInput and Router itself
    mock_flow.component_groups = [
        [
            MagicMock(spec=ComponentBase, module_info={"class_name": "BrokerInput"})
        ],  # Mock BrokerInput
        [
            MagicMock(
                spec=ComponentBase, module_info={"class_name": "SubscriptionRouter"}
            )
        ],  # Mock Router itself
        [mock_comp_a],  # Group for comp_a
        [mock_comp_b],  # Group for comp_b
    ]

    app_components_config = [
        {
            "name": "comp_a",
            "subscriptions": [{"topic": "data/a/>"}, {"topic": "common/data"}],
        },
        {"name": "comp_b", "subscriptions": [{"topic": "data/b/*"}]},
    ]

    # Mock config access needed by router's __init__ and _build_targets
    mock_config = {
        "component_name": "test_router",
        "component_module": "subscription_router",
        "component_config": {"app_components_config_ref": app_components_config},
    }

    return mock_app, mock_config, mock_comp_a, mock_comp_b


@patch(
    "solace_ai_connector.components.component_base.ComponentBase.discard_current_message"
)
@patch("solace_ai_connector.flow.subscription_router.SubscriptionRouter.get_config")
@patch("solace_ai_connector.flow.subscription_router.SubscriptionRouter.get_app")
def test_subscription_router_routing_match_a(
    mock_get_app, mock_get_config, mock_discard, mock_router_dependencies
):
    """Tests routing when topic matches component A."""
    mock_app, mock_config, mock_comp_a, mock_comp_b = mock_router_dependencies
    mock_get_app.return_value = mock_app
    mock_get_config.side_effect = lambda key, default=None: mock_config[
        "component_config"
    ].get(key, default)

    router = SubscriptionRouter(config=mock_config, app=mock_app)  # Pass mock app

    # Manually verify targets were built correctly (optional, but good practice)
    assert len(router.component_targets) == 2
    assert router.component_targets[0][0] == mock_comp_a
    assert len(router.component_targets[0][1]) == 2  # Regex list for comp_a
    assert router.component_targets[1][0] == mock_comp_b
    assert len(router.component_targets[1][1]) == 1  # Regex list for comp_b

    mock_message = MagicMock(spec=Message)
    mock_message.get_topic.return_value = "data/a/subtopic"

    router.invoke(mock_message, {})

    mock_comp_a.enqueue.assert_called_once()
    # Check that the enqueued object is an Event containing the original message
    enqueued_event = mock_comp_a.enqueue.call_args[0][0]
    assert isinstance(enqueued_event, Event)
    assert enqueued_event.event_type == EventType.MESSAGE
    assert enqueued_event.data == mock_message

    mock_comp_b.enqueue.assert_not_called()


@patch(
    "solace_ai_connector.components.component_base.ComponentBase.discard_current_message"
)
@patch("solace_ai_connector.flow.subscription_router.SubscriptionRouter.get_config")
@patch("solace_ai_connector.flow.subscription_router.SubscriptionRouter.get_app")
def test_subscription_router_routing_match_b(
    mock_get_app, mock_get_config, mock_discard, mock_router_dependencies
):
    """Tests routing when topic matches component B."""
    mock_app, mock_config, mock_comp_a, mock_comp_b = mock_router_dependencies
    mock_get_app.return_value = mock_app
    mock_get_config.side_effect = lambda key, default=None: mock_config[
        "component_config"
    ].get(key, default)

    router = SubscriptionRouter(config=mock_config, app=mock_app)

    mock_message = MagicMock(spec=Message)
    mock_message.get_topic.return_value = "data/b/level1"  # Matches data/b/*

    router.invoke(mock_message, {})

    mock_comp_a.enqueue.assert_not_called()
    mock_comp_b.enqueue.assert_called_once()
    enqueued_event = mock_comp_b.enqueue.call_args[0][0]
    assert isinstance(enqueued_event, Event)
    assert enqueued_event.event_type == EventType.MESSAGE
    assert enqueued_event.data == mock_message


@patch(
    "solace_ai_connector.components.component_base.ComponentBase.discard_current_message"
)
@patch("solace_ai_connector.flow.subscription_router.SubscriptionRouter.get_config")
@patch("solace_ai_connector.flow.subscription_router.SubscriptionRouter.get_app")
def test_subscription_router_routing_no_match(
    mock_get_app, mock_get_config, mock_discard, mock_router_dependencies
):
    """Tests routing when topic matches no component."""
    mock_app, mock_config, mock_comp_a, mock_comp_b = mock_router_dependencies
    mock_get_app.return_value = mock_app
    mock_get_config.side_effect = lambda key, default=None: mock_config[
        "component_config"
    ].get(key, default)

    router = SubscriptionRouter(config=mock_config, app=mock_app)

    mock_message = MagicMock(spec=Message)
    mock_message.get_topic.return_value = "data/c/unknown"

    router.invoke(mock_message, {})

    mock_comp_a.enqueue.assert_not_called()
    mock_comp_b.enqueue.assert_not_called()
    mock_discard.assert_called_once()


# 5.2.5 Test ComponentBase.get_config hierarchy
@pytest.fixture
def mock_component_for_get_config():
    """Fixture to create a mock component with parent app for get_config tests."""
    mock_app = MagicMock(spec=App)
    # Mock the app's get_config method
    app_level_config = {"app_param": "app_value", "shared_param": "app_shared"}
    mock_app.get_config = MagicMock(
        side_effect=lambda key, default=None: app_level_config.get(key, default)
    )

    # Mock ComponentBase instance
    mock_component = MagicMock(spec=ComponentBase)
    mock_component.parent_app = mock_app
    mock_component.get_app = MagicMock(
        return_value=mock_app
    )  # Ensure get_app returns the mock app

    # Define component-specific and flow-level configs
    mock_component.component_config = {
        "comp_param": "comp_value",
        "shared_param": "comp_shared",
    }
    mock_component.config = {
        "flow_param": "flow_value",
        "shared_param": "flow_shared",
    }  # Represents the component's entry in the flow config

    # Bind the real get_config method to the mock instance
    mock_component.get_config = ComponentBase.get_config.__get__(
        mock_component, ComponentBase
    )

    return mock_component


def test_get_config_hierarchy_comp_level(mock_component_for_get_config):
    """Test getting config defined only at component level."""
    assert mock_component_for_get_config.get_config("comp_param") == "comp_value"


def test_get_config_hierarchy_app_level(mock_component_for_get_config):
    """Test getting config defined only at app level."""
    assert mock_component_for_get_config.get_config("app_param") == "app_value"


def test_get_config_hierarchy_flow_level(mock_component_for_get_config):
    """Test getting config defined only at flow (self.config) level."""
    assert mock_component_for_get_config.get_config("flow_param") == "flow_value"


def test_get_config_hierarchy_precedence(mock_component_for_get_config):
    """Test precedence: component > app > flow."""
    assert (
        mock_component_for_get_config.get_config("shared_param") == "comp_shared"
    )  # Component overrides App and Flow

    # Remove from component_config to test app precedence
    del mock_component_for_get_config.component_config["shared_param"]
    assert (
        mock_component_for_get_config.get_config("shared_param") == "app_shared"
    )  # App overrides Flow

    # Remove from app_config to test flow precedence
    mock_component_for_get_config.parent_app.get_config = MagicMock(
        side_effect=lambda key, default=None: {"app_param": "app_value"}.get(
            key, default
        )
    )  # Simulate removal
    assert (
        mock_component_for_get_config.get_config("shared_param") == "flow_shared"
    )  # Flow is last resort


def test_get_config_hierarchy_not_found(mock_component_for_get_config):
    """Test getting config when key is not found."""
    assert mock_component_for_get_config.get_config("non_existent_param") is None
    assert (
        mock_component_for_get_config.get_config("non_existent_param", "default_val")
        == "default_val"
    )
