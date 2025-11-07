"""Test component configuration validation"""

import pytest
from unittest.mock import Mock
from solace_ai_connector.components.component_base import ComponentBase

def test_component_name_not_string_raises_error():
    """Test that component_name must be a string"""
    module_info = {
        "class_name": "TestComponent",
        "description": "Test component",
    }

    config = {
        "component_name": 123,  # Wrong type - should be string
        "component_module": "pass_through",
    }

    with pytest.raises(ValueError) as exc_info:
        ComponentBase(
            module_info,
            config=config,
            flow_name="test_flow",
            stop_signal=Mock(),
            error_queue=Mock(),
            instance_name="test_instance",
        )

    error_message = str(exc_info.value)
    assert "'component_name' must be a string" in error_message

def test_component_module_not_string_raises_error():
    """Test that component_module must be a string"""
    module_info = {
        "class_name": "TestComponent",
        "description": "Test component",
    }

    config = {
        "component_name": "test_component",
        "component_module": ["pass_through"],  # Wrong type - should be string
    }

    with pytest.raises(ValueError) as exc_info:
        ComponentBase(
            module_info,
            config=config,
            flow_name="test_flow",
            stop_signal=Mock(),
            error_queue=Mock(),
            instance_name="test_instance",
        )

    error_message = str(exc_info.value)
    assert "'component_module' must be a string" in error_message


def test_component_config_not_dict_raises_error():
    """Test that component_config must be a dictionary if provided"""
    module_info = {
        "class_name": "TestComponent",
        "description": "Test component",
    }

    config = {
        "component_name": "test_component",
        "component_module": "pass_through",
        "component_config": "invalid",  # Wrong type - should be dict
    }

    with pytest.raises(ValueError) as exc_info:
        ComponentBase(
            module_info,
            config=config,
            flow_name="test_flow",
            stop_signal=Mock(),
            error_queue=Mock(),
            instance_name="test_instance",
        )

    error_message = str(exc_info.value)
    assert "'component_config' must be a dictionary" in error_message


def test_component_config_as_dict_succeeds():
    """Test that component_config as a dict works correctly"""
    module_info = {
        "class_name": "TestComponent",
        "description": "Test component",
    }

    config = {
        "component_name": "test_component",
        "component_module": "pass_through",
        "component_config": {"key": "value"},  # Correct type
    }

    component = ComponentBase(
        module_info,
        config=config,
        flow_name="test_flow",
        stop_signal=Mock(),
        error_queue=Mock(),
        instance_name="test_instance",
    )

    assert component.component_config == {"key": "value"}


def test_input_transforms_not_list_raises_error():
    """Test that input_transforms must be a list if provided"""
    module_info = {
        "class_name": "TestComponent",
        "description": "Test component",
    }

    config = {
        "component_name": "test_component",
        "component_module": "pass_through",
        "input_transforms": {"type": "copy"},  # Wrong type - should be list
    }

    with pytest.raises(ValueError) as exc_info:
        ComponentBase(
            module_info,
            config=config,
            flow_name="test_flow",
            stop_signal=Mock(),
            error_queue=Mock(),
            instance_name="test_instance",
        )

    error_message = str(exc_info.value)
    assert "'input_transforms' must be a list" in error_message


def test_input_transforms_as_list_succeeds():
    """Test that input_transforms as a list works correctly"""
    module_info = {
        "class_name": "TestComponent",
        "description": "Test component",
    }

    config = {
        "component_name": "test_component",
        "component_module": "pass_through",
        "input_transforms": [
            {
                "type": "copy",
                "source_expression": "input.payload",
                "dest_expression": "user_data.request:payload",
            }
        ],
    }

    component = ComponentBase(
        module_info,
        config=config,
        flow_name="test_flow",
        stop_signal=Mock(),
        error_queue=Mock(),
        instance_name="test_instance",
    )

    assert component.config.get("input_transforms")[0].get("type") == "copy"


def test_input_selection_as_list_raises_error():
    """Test that input_selection as a list raises a clear error"""
    module_info = {
        "class_name": "TestComponent",
        "description": "Test component",
    }

    config = {
        "component_name": "test_component",
        "component_module": "pass_through",
        "input_selection": [  # This is WRONG - should be a dict
            {"source_expression": "user_data.output"}
        ],
    }

    with pytest.raises(ValueError) as exc_info:
        ComponentBase(
            module_info,
            config=config,
            flow_name="test_flow",
            stop_signal=Mock(),
            error_queue=Mock(),
            instance_name="test_instance",
        )

    error_message = str(exc_info.value)
    assert "'input_selection' must be a dictionary" in error_message
    assert "test_component" in error_message
    assert "source_expression" in error_message


def test_input_selection_as_dict_succeeds():
    """Test that input_selection as a dict works correctly"""
    module_info = {
        "class_name": "TestComponent",
        "description": "Test component",
    }

    config = {
        "component_name": "test_component",
        "component_module": "pass_through",
        "input_selection": {"source_expression": "user_data.output"},  # This is CORRECT
    }

    # This should not raise an error
    component = ComponentBase(
        module_info,
        config=config,
        flow_name="test_flow",
        stop_signal=Mock(),
        error_queue=Mock(),
        instance_name="test_instance",
    )

    assert component.config.get("input_selection") == {
        "source_expression": "user_data.output"
    }


def test_input_selection_as_string_raises_error():
    """Test that input_selection as a string raises a clear error"""
    module_info = {
        "class_name": "TestComponent",
        "description": "Test component",
    }

    config = {
        "component_name": "test_component",
        "component_module": "pass_through",
        "input_selection": "user_data.output",  # This is WRONG - should be a dict
    }

    with pytest.raises(ValueError) as exc_info:
        ComponentBase(
            module_info,
            config=config,
            flow_name="test_flow",
            stop_signal=Mock(),
            error_queue=Mock(),
            instance_name="test_instance",
        )

    error_message = str(exc_info.value)
    assert "'input_selection' must be a dictionary" in error_message
    assert "test_component" in error_message


def test_no_input_selection_succeeds():
    """Test that missing input_selection is allowed (uses default)"""
    module_info = {
        "class_name": "TestComponent",
        "description": "Test component",
    }

    config = {
        "component_name": "test_component",
        "component_module": "pass_through",
        # No input_selection specified - should use default
    }

    # This should not raise an error
    component = ComponentBase(
        module_info,
        config=config,
        flow_name="test_flow",
        stop_signal=Mock(),
        error_queue=Mock(),
        instance_name="test_instance",
    )

    assert component.config.get("input_selection") is None

def test_num_instances_not_int_raises_error():
    """Test that num_instances must be an integer if provided"""
    module_info = {
        "class_name": "TestComponent",
        "description": "Test component",
    }
    
    config = {
        "component_name": "test_component",
        "component_module": "pass_through",
        "num_instances": "5",  # Wrong type - should be int
    }
    
    with pytest.raises(ValueError) as exc_info:
        ComponentBase(
            module_info,
            config=config,
            flow_name="test_flow",
            stop_signal=Mock(),
            error_queue=Mock(),
            instance_name="test_instance",
        )
    
    error_message = str(exc_info.value)
    assert "'num_instances' must be an integer" in error_message


def test_num_instances_as_int_succeeds():
    """Test that num_instances as an integer works correctly"""
    module_info = {
        "class_name": "TestComponent",
        "description": "Test component",
    }
    
    config = {
        "component_name": "test_component",
        "component_module": "pass_through",
        "num_instances": 3,  # Correct type
    }
    
    component = ComponentBase(
        module_info,
        config=config,
        flow_name="test_flow",
        stop_signal=Mock(),
        error_queue=Mock(),
        instance_name="test_instance",
    )
    
    assert component.config.get("num_instances") == 3


def test_component_class_not_string_raises_error():
    """Test that component_class must be a string if provided"""
    module_info = {
        "class_name": "TestComponent",
        "description": "Test component",
    }
    
    config = {
        "component_name": "test_component",
        "component_module": "pass_through",
        "component_class": 123,  # Wrong type - should be string
    }
    
    with pytest.raises(ValueError) as exc_info:
        ComponentBase(
            module_info,
            config=config,
            flow_name="test_flow",
            stop_signal=Mock(),
            error_queue=Mock(),
            instance_name="test_instance",
        )
    
    error_message = str(exc_info.value)
    assert "'component_class' must be a type" in error_message


def test_component_class_as_string_succeeds():
    """Test that component_class as a string works correctly"""
    module_info = {
        "class_name": "TestComponent",
        "description": "Test component",
    }
    class DummyClass(ComponentBase):
        pass
    
    config = {
        "component_name": "test_component",
        "component_module": "pass_through",
        "component_class": DummyClass,  # Correct type
    }
    
    component = ComponentBase(
        module_info,
        config=config,
        flow_name="test_flow",
        stop_signal=Mock(),
        error_queue=Mock(),
        instance_name="test_instance",
    )
    
    assert component.config.get("component_class") == DummyClass


def test_broker_request_response_not_dict_raises_error():
    """Test that broker_request_response must be a dictionary if provided"""
    module_info = {
        "class_name": "TestComponent",
        "description": "Test component",
    }
    
    config = {
        "component_name": "test_component",
        "component_module": "pass_through",
        "broker_request_response": "enabled",  # Wrong type - should be dict
    }
    
    with pytest.raises(ValueError) as exc_info:
        ComponentBase(
            module_info,
            config=config,
            flow_name="test_flow",
            stop_signal=Mock(),
            error_queue=Mock(),
            instance_name="test_instance",
        )
    
    error_message = str(exc_info.value)
    assert "'broker_request_response' must be a dictionary" in error_message


def test_broker_request_response_as_dict_succeeds():
    """Test that broker_request_response as a dictionary works correctly"""
    module_info = {
        "class_name": "TestComponent",
        "description": "Test component",
    }
    
    config = {
        "component_name": "test_component",
        "component_module": "pass_through",
        "broker_request_response": {"enabled": False},  # Correct type
    }
    
    component = ComponentBase(
        module_info,
        config=config,
        flow_name="test_flow",
        stop_signal=Mock(),
        error_queue=Mock(),
        instance_name="test_instance",
    )
    
    assert component.broker_request_response_config == {"enabled": False}



def test_valid_component_config_succeeds():
    """Test that a fully valid component configuration works"""
    module_info = {
        "class_name": "TestComponent",
        "description": "Test component",
    }

    config = {
        "component_name": "test_component",
        "component_module": "pass_through",
        "component_config": {"timeout": 5000},
        "input_transforms": [
            {
                "type": "copy",
                "source_expression": "input.payload",
                "dest_expression": "user_data.request:payload",
            }
        ],
        "input_selection": {"source_expression": "user_data.output"},
    }

    component = ComponentBase(
        module_info,
        config=config,
        flow_name="test_flow",
        stop_signal=Mock(),
        error_queue=Mock(),
        instance_name="test_instance",
    )

    assert component.name == "test_component"
    assert component.component_config == {"timeout": 5000}
    assert component.config.get("input_transforms") == [
        {
            "type": "copy",
            "source_expression": "input.payload",
            "dest_expression": "user_data.request:payload",
        }
    ]
    assert component.config.get("input_selection") == {
        "source_expression": "user_data.output"
    }
