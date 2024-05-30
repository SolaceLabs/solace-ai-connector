"""This file tests the input_transforms configuration and execution"""

import sys

sys.path.append("src")

from utils_for_test_files import (  # pylint: disable=wrong-import-position
    create_connector,
    create_and_run_component,
    # dispose_connector,
)
from solace_ai_connector.common.message import (  # pylint: disable=wrong-import-position
    Message,
)


def test_basic_copy_transform():
    """Test the basic copy transform"""
    # Create a simple configuration
    config_yaml = """
flows:
  - name: test_flow
    components:
      - component_name: pass_through
        component_module: pass_through
        input_transforms:
          - type: copy
            source_expression: input.payload
            dest_expression: user_data.temp:payload
          - type: copy
            source_value: "Static Greeting!"
            dest_expression: user_data.temp:payload.greeting
        component_input:
          source_expression: user_data.temp:payload.text
"""

    message = Message(payload={"text": "Hello, World!"})
    output_message = create_and_run_component(config_yaml, message)

    # Check the output
    assert output_message.get_data("user_data.temp") == {
        "payload": {"text": "Hello, World!", "greeting": "Static Greeting!"}
    }
    assert output_message.get_data("previous") == "Hello, World!"


def test_basic_map_transform():
    """Test the basic map transform"""
    # Create a simple configuration
    config_yaml = """
flows:
  - name: test_flow
    components:
      - component_name: pass_through
        component_module: pass_through
        input_transforms:
          - type: map
            source_list_expression: input.payload:my_list
            source_expression: item:one
            dest_list_expression: user_data.temp:my_list
            dest_expression: my_obj.item
          - type: map
            source_list_expression: input.payload:my_list
            source_expression: item
            dest_list_expression: user_data.temp:my_list
            dest_expression: my_obj.full
        component_input:
          source_expression: user_data.temp
"""

    message = Message(payload={"my_list": [{"one": 1}, {"one": 2}, {"one": 3}]})
    output_message = create_and_run_component(config_yaml, message)

    # Check the output
    assert output_message.get_data("user_data.temp") == {
        "my_list": [
            {"my_obj": {"item": 1, "full": {"one": 1}}},
            {"my_obj": {"item": 2, "full": {"one": 2}}},
            {"my_obj": {"item": 3, "full": {"one": 3}}},
        ]
    }


def test_map_with_index_transform():
    """Test the map transform with index"""
    # Create a simple configuration
    config_yaml = """
flows:
  - name: test_flow
    components:
      - component_name: pass_through
        component_module: pass_through
        input_transforms:
          - type: map
            source_list_expression: input.payload:my_list
            source_expression: item:one
            dest_list_expression: user_data.temp:my_list
            dest_expression: my_obj.item
          - type: map
            source_list_expression: input.payload:my_list
            source_expression: index
            dest_list_expression: user_data.temp:my_list
            dest_expression: my_obj.index
        component_input:
          source_expression: user_data.temp
"""

    message = Message(payload={"my_list": [{"one": 1}, {"one": 2}, {"one": 3}]})
    output_message = create_and_run_component(config_yaml, message)

    # Check the output
    assert output_message.get_data("user_data.temp") == {
        "my_list": [
            {"my_obj": {"item": 1, "index": 0}},
            {"my_obj": {"item": 2, "index": 1}},
            {"my_obj": {"item": 3, "index": 2}},
        ]
    }


def test_map_with_message_source_expression():
    """Test the map transform with message source expression"""
    # Create a simple configuration
    config_yaml = """
flows:
  - name: test_flow
    components:
      - component_name: pass_through
        component_module: pass_through
        input_transforms:
          - type: map
            source_list_expression: input.payload:my_list
            source_expression: item:one
            dest_list_expression: user_data.temp:my_list
            dest_expression: my_obj.item
          - type: map
            source_list_expression: input.payload:my_list
            source_expression: input.payload:my_obj.two
            dest_list_expression: user_data.temp:my_list
            dest_expression: my_obj.my_obj_two
        component_input:
          source_expression: user_data.temp
"""

    message = Message(
        payload={"my_list": [{"one": 1}, {"one": 2}, {"one": 3}], "my_obj": {"two": 2}}
    )
    output_message = create_and_run_component(config_yaml, message)

    # Check the output
    assert output_message.get_data("user_data.temp") == {
        "my_list": [
            {"my_obj": {"item": 1, "my_obj_two": 2}},
            {"my_obj": {"item": 2, "my_obj_two": 2}},
            {"my_obj": {"item": 3, "my_obj_two": 2}},
        ]
    }


def test_basic_append_transform():
    """Test the basic append transform"""
    # Create a simple configuration
    config_yaml = """
flows:
  - name: test_flow
    components:
      - component_name: pass_through
        component_module: pass_through
        input_transforms:
          - type: append
            source_expression: input.payload:one
            dest_expression: user_data.temp:my_list
          - type: append
            source_expression: input.payload:two
            dest_expression: user_data.temp:my_list
          - type: append
            source_expression: input.payload:three
            dest_expression: user_data.temp:my_list
        component_input:
          source_expression: user_data.temp
"""

    message = Message(payload={"one": 1, "two": 2, "three": 3})
    output_message = create_and_run_component(config_yaml, message)

    # Check the output
    assert output_message.get_data("user_data.temp") == {"my_list": [1, 2, 3]}
    assert output_message.get_data("previous") == {"my_list": [1, 2, 3]}


def test_overwrite_non_list_with_list():
    """Test that a non-list value is overwritten by a list"""
    # Create a simple configuration
    config_yaml = """
flows:
  - name: test_flow
    components:
      - component_name: pass_through
        component_module: pass_through
        input_transforms:
          - type: copy
            source_expression: input.payload:one
            dest_expression: user_data.temp:my_list
          - type: append
            source_expression: input.payload:one
            dest_expression: user_data.temp:my_list
        component_input:
          source_expression: user_data.temp
"""

    message = Message(payload={"one": 1})
    output_message = create_and_run_component(config_yaml, message)

    # Check the output
    assert output_message.get_data("user_data.temp") == {"my_list": [1]}
    assert output_message.get_data("previous") == {"my_list": [1]}


def test_transform_without_a_type():
    """Test that the program exits if a transform does not have a type"""
    try:
        config_yaml = """
flows:
  - name: test_flow
    components:
      - component_name: pass_through
        component_module: pass_through
        input_transforms:
          - source_expression: input.payload:one
            dest_expression: user_data.temp:my_list
        component_input:
          source_expression: user_data.temp
"""
        create_connector(config_yaml)
    except ValueError as e:
        assert str(e) == "Transform at index 0 does not have a type"


def test_transform_with_unknown_type():
    """Test that the program exits if a transform has an unknown type"""
    try:
        config_yaml = """
flows:
  - name: test_flow
    components:
      - component_name: pass_through
        component_module: pass_through
        input_transforms:
          - type: unknown
            source_expression: input.payload:one
            dest_expression: user_data.temp:my_list
        component_input:
          source_expression: user_data.temp
"""
        create_connector(config_yaml)
    except ValueError as e:
        assert str(e) == "Transform at index 0 has an unknown type: unknown"


def test_missing_source_expression():
    """Test that the program exits if no source expression is provided"""
    try:
        config_yaml = """
instance_name: test_instance
flows:
  - name: test_flow
    components:
      - component_name: pass_through
        component_module: pass_through
        input_transforms:
          - type: copy
            dest_expression: user_data.temp:my_list
        component_input:
          source_expression: user_data.temp
"""
        create_connector(config_yaml)
    except ValueError as e:
        assert str(e).endswith("Transform does not have a source expression")


def test_missing_dest_expression():
    """Test that the program exits if no dest expression is provided"""
    try:
        config_yaml = """
instance_name: test_instance
flows:
  - name: test_flow
    components:
      - component_name: pass_through
        component_module: pass_through
        input_transforms:
          - type: copy
            source_expression: input.payload:one
        component_input:
          source_expression: user_data.temp
"""
        create_connector(config_yaml)
    except ValueError as e:
        assert str(e).endswith("Transform does not have a dest expression")


def test_source_value_as_an_object():
    """Test that a source value can be an object"""
    # Create a simple configuration
    config_yaml = """
flows:
  - name: test_flow
    components:
      - component_name: pass_through
        component_module: pass_through
        input_transforms:
          - type: copy
            source_value:
              one: 1
              two: 2
            dest_expression: user_data.temp:my_obj
        component_input:
          source_expression: user_data.temp
"""

    message = Message()
    output_message = create_and_run_component(config_yaml, message)

    # Check the output
    assert output_message.get_data("user_data.temp") == {"my_obj": {"one": 1, "two": 2}}
    assert output_message.get_data("previous") == {"my_obj": {"one": 1, "two": 2}}
