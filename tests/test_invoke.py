"""This file tests the utils functions that execute the invoke configuration specification"""

import sys
import pytest

sys.path.append("src")


from solace_ai_connector.test_utils.utils_for_test_files import (
    create_and_run_component,
)
from solace_ai_connector.common.utils import (
    resolve_config_values,
)
from solace_ai_connector.common.message import (
    Message,
)


# A list of configuration to test the resolve_config_values function
tests = [
    # A simple config with no invoke
    {
        "input": {
            "a": 1,
            "b": 2,
            "c": 3,
        },
        "expected": {
            "a": 1,
            "b": 2,
            "c": 3,
        },
    },
    # A simple config with an invoke
    {
        "input": {
            "a": 1,
            "b": 2,
            "c": {
                "invoke": {
                    "module": "invoke_functions",
                    "function": "add",
                    "params": {
                        "x": 1,
                        "y": 2,
                    },
                },
            },
        },
        "expected": {
            "a": 1,
            "b": 2,
            "c": 3,
        },
    },
    # A nested config with an invoke
    {
        "input": {
            "a": 1,
            "b": 2,
            "c": {
                "d": 3,
                "e": {
                    "invoke": {
                        "module": "invoke_functions",
                        "function": "add",
                        "params": {
                            "x": 1,
                            "y": 2,
                        },
                    },
                },
            },
        },
        "expected": {
            "a": 1,
            "b": 2,
            "c": {
                "d": 3,
                "e": 3,
            },
        },
    },
    # A list of config with an invoke
    {
        "input": {
            "a": 1,
            "b": 2,
            "c": [
                3,
                {
                    "invoke": {
                        "module": "invoke_functions",
                        "function": "add",
                        "params": {
                            "x": 1,
                            "y": 2,
                        },
                    },
                },
            ],
        },
        "expected": {
            "a": 1,
            "b": 2,
            "c": [
                3,
                3,
            ],
        },
    },
    # A list of config with an invoke
    {
        "input": {
            "a": 1,
            "b": 2,
            "c": [
                3,
                {
                    "d": 4,
                    "e": {
                        "invoke": {
                            "module": "invoke_functions",
                            "function": "add",
                            "params": {
                                "x": 1,
                                "y": 2,
                            },
                        },
                    },
                },
            ],
        },
        "expected": {
            "a": 1,
            "b": 2,
            "c": [
                3,
                {
                    "d": 4,
                    "e": 3,
                },
            ],
        },
    },
    # Test all the invoke functions
    {
        "input": {
            "a": 1,
            "b": 2,
            "c": {
                "add": {
                    "invoke": {
                        "module": "invoke_functions",
                        "function": "add",
                        "params": {
                            "positional": [1, 2],
                        },
                    },
                },
                "subtract": {
                    "invoke": {
                        "module": "invoke_functions",
                        "function": "subtract",
                        "params": {
                            "positional": [1, 2],
                        },
                    },
                },
                "multiply": {
                    "invoke": {
                        "module": "invoke_functions",
                        "function": "multiply",
                        "params": {
                            "positional": [1, 2],
                        },
                    },
                },
                "divide": {
                    "invoke": {
                        "module": "invoke_functions",
                        "function": "divide",
                        "params": {
                            "positional": [1, 2],
                        },
                    },
                },
                "modulus": {
                    "invoke": {
                        "module": "invoke_functions",
                        "function": "modulus",
                        "params": {
                            "positional": [1, 2],
                        },
                    },
                },
                "power": {
                    "invoke": {
                        "module": "invoke_functions",
                        "function": "power",
                        "params": {
                            "positional": [1, 2],
                        },
                    },
                },
                "equal": {
                    "invoke": {
                        "module": "invoke_functions",
                        "function": "equal",
                        "params": {
                            "positional": [1, 2],
                        },
                    },
                },
                "not_equal": {
                    "invoke": {
                        "module": "invoke_functions",
                        "function": "not_equal",
                        "params": {
                            "positional": [1, 2],
                        },
                    },
                },
                "greater_than": {
                    "invoke": {
                        "module": "invoke_functions",
                        "function": "greater_than",
                        "params": {
                            "positional": [1, 2],
                        },
                    },
                },
                "less_than": {
                    "invoke": {
                        "module": "invoke_functions",
                        "function": "less_than",
                        "params": {
                            "positional": [1, 2],
                        },
                    },
                },
                "greater_than_or_equal": {
                    "invoke": {
                        "module": "invoke_functions",
                        "function": "greater_than_or_equal",
                        "params": {
                            "positional": [1, 2],
                        },
                    },
                },
                "less_than_or_equal": {
                    "invoke": {
                        "module": "invoke_functions",
                        "function": "less_than_or_equal",
                        "params": {
                            "positional": [1, 2],
                        },
                    },
                },
                "and_op": {
                    "invoke": {
                        "module": "invoke_functions",
                        "function": "and_op",
                        "params": {
                            "positional": [True, False],
                        },
                    },
                },
                "or_op": {
                    "invoke": {
                        "module": "invoke_functions",
                        "function": "or_op",
                        "params": {
                            "positional": [True, False],
                        },
                    },
                },
                "not_op": {
                    "invoke": {
                        "module": "invoke_functions",
                        "function": "not_op",
                        "params": {
                            "positional": [True],
                        },
                    },
                },
                "in_op": {
                    "invoke": {
                        "module": "invoke_functions",
                        "function": "in_op",
                        "params": {
                            "positional": [1, [1, 2, 3]],
                        },
                    },
                },
                "negate": {
                    "invoke": {
                        "module": "invoke_functions",
                        "function": "negate",
                        "params": {
                            "positional": [1],
                        },
                    },
                },
                "if_else_true": {
                    "invoke": {
                        "module": "invoke_functions",
                        "function": "if_else",
                        "params": {
                            "positional": [True, 1, 2],
                        },
                    },
                },
                "if_else_false": {
                    "invoke": {
                        "module": "invoke_functions",
                        "function": "if_else",
                        "params": {
                            "positional": [False, 1, 2],
                        },
                    },
                },
            },
        },
        "expected": {
            "a": 1,
            "b": 2,
            "c": {
                "add": 3,
                "subtract": -1,
                "multiply": 2,
                "divide": 0.5,
                "modulus": 1,
                "power": 1,
                "equal": False,
                "not_equal": True,
                "greater_than": False,
                "less_than": True,
                "greater_than_or_equal": False,
                "less_than_or_equal": True,
                "and_op": False,
                "or_op": True,
                "not_op": False,
                "in_op": True,
                "negate": -1,
                "if_else_true": 1,
                "if_else_false": 2,
            },
        },
    },
]


# Test the resolve_config_values function
@pytest.mark.parametrize("test", tests)
def test_resolve_config_values(test):
    assert resolve_config_values(test["input"]) == test["expected"]


# Test the resolve_config_values function with a missing module
def test_resolve_config_values_missing_module():
    with pytest.raises(ImportError, match="Module 'missing_module' not found"):
        resolve_config_values(
            {
                "a": {
                    "invoke": {
                        "module": "missing_module",
                        "function": "add",
                        "params": {
                            "x": 1,
                            "y": 2,
                        },
                    },
                },
            }
        )


# Test the resolve_config_values function with a missing function
def test_resolve_config_values_missing_function():
    with pytest.raises(
        AttributeError,
        match="module 'solace_ai_connector.common.invoke_functions' has no attribute 'missing'",
    ):
        resolve_config_values(
            {
                "a": {
                    "invoke": {
                        "module": "invoke_functions",
                        "function": "missing",
                        "params": {
                            "x": 1,
                            "y": 2,
                        },
                    },
                },
            }
        )


# Test the resolve_config_values function with a missing attribute
def test_resolve_config_values_missing_attribute():
    with pytest.raises(
        AttributeError,
        match="module 'solace_ai_connector.common.invoke_functions' has no attribute 'missing'",
    ):
        resolve_config_values(
            {
                "a": {
                    "invoke": {
                        "module": "invoke_functions",
                        "attribute": "missing",
                    },
                },
            }
        )


# Test the resolve_config_values function with both module and object
def test_resolve_config_values_missing_object():
    with pytest.raises(ValueError, match="Cannot have both module and object"):
        resolve_config_values(
            {
                "a": {
                    "invoke": {
                        "module": "invoke_functions",
                        "object": "add",
                        "attribute": "missing",
                    },
                },
            }
        )


# Test calling a function in the global space
def test_resolve_config_values_global_function():
    assert resolve_config_values(
        {
            "a": {
                "invoke": {
                    "function": "len",
                    "params": {
                        "positional": [[1, 2, 3]],
                    },
                },
            },
        }
    ) == {"a": 3}


def test_resolve_config_values_missing_global_function():
    with pytest.raises(
        ValueError, match="Function 'missing' not a known python function"
    ):
        resolve_config_values(
            {
                "a": {
                    "invoke": {
                        "function": "missing",
                    },
                },
            }
        )


def test_call_function_no_params():
    assert (
        resolve_config_values(
            {
                "a": {
                    "invoke": {
                        "function": "locals",
                    },
                },
            }
        )
        is not None
    )


def test_invoke_params_bad_positional():
    """Verify that an error is raised if the positional parameter is not a list"""
    with pytest.raises(ValueError, match="positional must be a list"):
        resolve_config_values(
            {
                "a": {
                    "invoke": {
                        "module": "invoke_functions",
                        "function": "add",
                        "params": {
                            "positional": 1,
                        },
                    },
                },
            }
        )


def test_invoke_params_bad_keyword():
    """Verify that an error is raised if the keyword parameter is not a dict"""
    with pytest.raises(ValueError, match="keyword must be a dict"):
        resolve_config_values(
            {
                "a": {
                    "invoke": {
                        "module": "invoke_functions",
                        "function": "add",
                        "params": {
                            "keyword": 1,
                        },
                    },
                },
            }
        )


def test_invoke_params_with_both_positional_and_keyword():
    """Verify that both positional and keyword parameters work as expected"""
    assert resolve_config_values(
        {
            "a": {
                "invoke": {
                    "module": "invoke_functions",
                    "function": "_test_positional_and_keyword_args",
                    "params": {
                        "positional": [1, 2],
                        "keyword": {"x": 1, "y": 2},
                    },
                },
            },
        }
    ) == {"a": ((1, 2), {"x": 1, "y": 2})}


def test_invoke_params_with_positional():
    """Verify that positional parameters work as expected"""
    assert resolve_config_values(
        {
            "a": {
                "invoke": {
                    "module": "invoke_functions",
                    "function": "_test_positional_args",
                    "params": {
                        "positional": [1, 2],
                    },
                },
            },
        }
    ) == {"a": (1, 2)}


def test_invoke_params_with_keyword():
    """Verify that keyword parameters work as expected"""
    assert resolve_config_values(
        {
            "a": {
                "invoke": {
                    "module": "invoke_functions",
                    "function": "_test_keyword_args",
                    "params": {
                        "keyword": {"x": 1, "y": 2},
                    },
                },
            },
        }
    ) == {"a": {"x": 1, "y": 2}}


def test_invoke_import_os_module():
    """Verify that the os module can be imported"""
    assert resolve_config_values(
        {
            "a": {
                "invoke": {
                    "module": "os",
                    "attribute": "name",
                },
            },
        }
    ) == {"a": "posix"}


def test_invoke_with_evaluate_expression_simple():
    """Verify that the evaluate expression is evaluated"""
    config = resolve_config_values(
        {
            "source_expression": {
                "invoke": {
                    "module": "invoke_functions",
                    "function": "add",
                    "params": {
                        "positional": [
                            "evaluate_expression(input.payload:my_obj.val1)",
                            "evaluate_expression(input.payload:my_obj.val2)",
                        ],
                    },
                },
            },
        }
    )
    message = Message(payload={"my_obj": {"val1": 1, "val2": 2}})
    config["source_expression"] = config["source_expression"](message)
    assert config == {"source_expression": 3}


def test_invoke_with_evaluate_expression_cast_to_int():
    """Verify that the evaluate expression is evaluated"""
    config = resolve_config_values(
        {
            "source_expression": {
                "invoke": {
                    "module": "invoke_functions",
                    "function": "add",
                    "params": {
                        "positional": [
                            "evaluate_expression(input.payload:my_obj.val1, int )",
                            2,
                        ],
                    },
                },
            },
        }
    )
    message = Message(payload={"my_obj": {"val1": "1"}})
    config["source_expression"] = config["source_expression"](message)
    assert config == {"source_expression": 3}


def test_invoke_with_evaluate_expression_cast_to_float():
    """Verify that the evaluate expression is evaluated"""
    config = resolve_config_values(
        {
            "source_expression": {
                "invoke": {
                    "module": "invoke_functions",
                    "function": "add",
                    "params": {
                        "positional": [
                            "evaluate_expression(input.payload:my_obj.val1, float )",
                            2,
                        ],
                    },
                },
            },
        }
    )
    message = Message(payload={"my_obj": {"val1": "1.1"}})
    config["source_expression"] = config["source_expression"](message)
    assert config == {"source_expression": 3.1}


def test_invoke_with_source_expression_cast_to_bool():
    """Verify that the source expression is evaluated"""
    config = resolve_config_values(
        {
            "source_expression": {
                "invoke": {
                    "module": "invoke_functions",
                    "function": "and_op",
                    "params": {
                        "positional": [
                            "evaluate_expression(input.payload:my_obj.val1 , bool )",
                            True,
                        ],
                    },
                },
            },
        }
    )
    message = Message(payload={"my_obj": {"val1": "True"}})
    config["source_expression"] = config["source_expression"](message)
    assert config == {"source_expression": True}


def test_invoke_with_evaluate_expression_cast_to_str():
    """Verify that the evaluate expression is evaluated"""
    config = resolve_config_values(
        {
            "source_expression": {
                "invoke": {
                    "module": "invoke_functions",
                    "function": "add",
                    "params": {
                        "positional": [
                            "evaluate_expression(input.payload:my_obj.val1,str)",
                            "2",
                        ],
                    },
                },
            },
        }
    )
    message = Message(payload={"my_obj": {"val1": 1}})
    config["source_expression"] = config["source_expression"](message)
    assert config == {"source_expression": "12"}


def test_invoke_with_evaluate_expression_keyword():
    """Verify that the evaluate expression is evaluated"""
    config = resolve_config_values(
        {
            "source_value": {
                "invoke": {
                    "module": "invoke_functions",
                    "function": "_test_keyword_args",
                    "params": {
                        "keyword": {
                            "x": "evaluate_expression(input.payload:my_obj.val1)",
                            "y": "evaluate_expression(input.payload:my_obj.val2)",
                        },
                    },
                },
            },
        }
    )
    message = Message(payload={"my_obj": {"val1": 1, "val2": 2}})
    config["source_value"] = config["source_value"](message)
    assert config == {"source_value": {"x": 1, "y": 2}}


def test_invoke_with_evaluate_expression_complex():
    """Verify that the evaluate expression is evaluated"""
    config = resolve_config_values(
        {
            "source_expression": {
                "invoke": {
                    "module": "invoke_functions",
                    "function": "_test_positional_and_keyword_args",
                    "params": {
                        "positional": [
                            "evaluate_expression(input.payload:my_obj.val1)",
                            {
                                "invoke": {
                                    "module": "invoke_functions",
                                    "function": "add",
                                    "params": {
                                        "positional": [
                                            "evaluate_expression(input.payload:my_obj.val2)",
                                            {
                                                "invoke": {
                                                    "module": "invoke_functions",
                                                    "function": "multiply",
                                                    "params": {
                                                        "positional": [
                                                            "evaluate_expression(input.payload:my_obj.val2)",
                                                            "evaluate_expression(input.payload:my_obj.val2)",
                                                        ],
                                                    },
                                                },
                                            },
                                        ],
                                    },
                                },
                            },
                        ],
                        "keyword": {
                            "x": "evaluate_expression(input.payload:my_obj.val1)",
                            "y": {
                                "invoke": {
                                    "module": "invoke_functions",
                                    "function": "subtract",
                                    "params": {
                                        "positional": [
                                            "evaluate_expression(input.payload:my_obj.val2)",
                                            "evaluate_expression(input.payload:my_obj.val3)",
                                        ],
                                    },
                                },
                            },
                        },
                    },
                },
            },
        }
    )
    message = Message(payload={"my_obj": {"val1": 1, "val2": 2, "val3": 3}})
    config["source_expression"] = config["source_expression"](message)
    assert config == {"source_expression": ((1, 6), {"x": 1, "y": -1})}


def test_invoke_with_evaluate_expression_missing():
    """Verify that the evaluate expression is evaluated"""
    config = resolve_config_values(
        {
            "source_expression": {
                "invoke": {
                    "module": "invoke_functions",
                    "function": "add",
                    "params": {
                        "positional": [
                            "evaluate_expression(input.payload:my_obj.val1)",
                            "evaluate_expression(input.payload:my_obj.val2)",
                        ],
                    },
                },
            },
        }
    )
    message = Message(payload={"my_obj": {"val1": 1}})
    with pytest.raises(
        TypeError, match=r"unsupported operand type\(s\) for \+: 'int' and 'NoneType'"
    ):
        config["source_expression"] = config["source_expression"](message)


def test_invoke_with_source_expression_no_evaluate_expression():
    """Verify that the evaluated expression is evaluated"""
    with pytest.raises(
        ValueError, match=r"evaluate_expression\(\) must contain an expression"
    ):
        resolve_config_values(
            {
                "source_expression": {
                    "invoke": {
                        "module": "invoke_functions",
                        "function": "add",
                        "params": {
                            "positional": [
                                "evaluate_expression()",
                                2,
                            ],
                        },
                    },
                },
            }
        )


def test_invoke_with_evaluate_expression_with_real_flow():
    """Verify that the evaluate expression is evaluated properly in transforms and input_selection"""
    config_yaml = """
instance_name: test_instance
log:
  log_file_level: DEBUG
  log_file: solace_ai_connector.log
flows:
  - name: test_flow
    components:
      - component_name: pass_through
        component_module: pass_through
        input_transforms:
          - type: copy
            source_value: 
              invoke:
                module: invoke_functions
                function: add
                params: 
                  positional: 
                    - evaluate_expression(input.payload:my_obj.val1.1)
                    - 2
            dest_expression: user_data.temp:my_val
        input_selection:
          source_expression: 
            invoke:
              module: invoke_functions
              function: add
              params: 
                positional: 
                  - evaluate_expression(input.payload:my_obj.obj2)
                  - " test"
"""
    message = Message(payload={"my_obj": {"val1": [1, 2, 3], "obj2": "Hello, World!"}})
    output_message = create_and_run_component(config_yaml, message)

    # Check the output
    assert output_message.get_data("user_data.temp") == {
        "my_val": 4
    }  # The copy transform
    assert (
        output_message.get_data("previous") == "Hello, World! test"
    )  # The input_selection


def atest_user_processing_component():
    """Test the basic copy transform"""
    # Create a simple configuration
    config_yaml = """
flows:
  - name: test_flow
    components:
      - component_name: user_processing
        component_module: user_processor
        component_processing:
          invoke:
            module: invoke_functions
            function: add
            params:
              positional:
                - evaluate_expression(input.payload:my_obj.val1.1)
                - 2
"""

    message = Message(payload={"my_obj": {"val1": [1, 2, 3], "obj2": "Hello, World!"}})
    output_message = create_and_run_component(config_yaml, message)

    # Check the output
    assert output_message.get_data("previous") == 4


def test_reduce_transform_accumulator():
    """Test the reduce transform with an accumulator"""
    config_yaml = """
instance_name: test_instance
log:
  log_file_level: DEBUG
  log_file: solace_ai_connector.log
flows:
  - name: test_flow
    components:
      - component_name: pass_through
        component_module: pass_through
        input_transforms:
          - type: reduce
            source_list_expression: input.payload:my_list
            initial_value: 0
            accumulator_function:
                invoke:
                    module: invoke_functions
                    function: add
                    params:
                        positional:
                            - evaluate_expression(keyword_args:accumulated_value)
                            - evaluate_expression(keyword_args:current_value)
            dest_expression: user_data.temp:my_val
        input_selection:
          source_expression: user_data.temp:my_val
"""
    message = Message(payload={"my_list": [1, 2, 3, 4, 5]})
    output_message = create_and_run_component(config_yaml, message)

    # Check the output
    assert output_message.get_data("user_data.temp") == {"my_val": 15}


def test_reduce_transform_make_list():
    """Test the reduce transform with an accumulator"""
    config_yaml = """
instance_name: test_instance
log:
  log_file_level: DEBUG
  log_file: solace_ai_connector.log
flows:
  - name: test_flow
    components:
      - component_name: pass_through
        component_module: pass_through
        input_transforms:
          - type: reduce
            source_list_expression: input.payload:my_list
            initial_value: 
              invoke:
                module: invoke_functions
                function: empty_list
            accumulator_function:
              invoke:
                module: invoke_functions
                function: append
                params:
                  positional:
                    - evaluate_expression(keyword_args:accumulated_value)
                    - evaluate_expression(keyword_args:current_value)
            dest_expression: user_data.temp:my_val
        input_selection:
          source_expression: user_data.temp:my_val
   """
    message = Message(payload={"my_list": [1, 2, 3, 4, 5]})
    output_message = create_and_run_component(config_yaml, message)

    # Check the output
    assert output_message.get_data("user_data.temp") == {"my_val": [1, 2, 3, 4, 5]}


def test_map_transform_add_2():
    """Test the map transform with a processing function"""
    config_yaml = """
instance_name: test_instance
log:
  log_file_level: DEBUG
  log_file: solace_ai_connector.log
flows:
  - name: test_flow
    components:
      - component_name: pass_through
        component_module: pass_through
        input_transforms:
          - type: map
            source_list_expression: input.payload:my_list
            processing_function:
              invoke:
                module: invoke_functions
                function: add
                params:
                  positional:
                    - evaluate_expression(keyword_args:current_value)
                    - 2
            dest_list_expression: user_data.temp:new_list
        input_selection:
          source_expression: user_data.temp:new_list
   """
    message = Message(payload={"my_list": [1, 2, 3, 4, 5]})
    output_message = create_and_run_component(config_yaml, message)

    # Check the output
    assert output_message.get_data("user_data.temp") == {"new_list": [3, 4, 5, 6, 7]}


def test_filter_transform_greater_than_2():
    """Test the filter transform with a filter function checking for values > 2"""
    config_yaml = """
instance_name: test_instance
log:
  log_file_level: DEBUG
  log_file: solace_ai_connector.log
flows:
  - name: test_flow
    components:
      - component_name: pass_through
        component_module: pass_through
        input_transforms:
          - type: filter
            source_list_expression: input.payload:my_list
            filter_function:
              invoke:
                module: invoke_functions
                function: greater_than
                params:
                  positional:
                    - evaluate_expression(keyword_args:current_value)
                    - 2
            dest_list_expression: user_data.temp:new_list
        input_selection:
          source_expression: user_data.temp:new_list
   """
    message = Message(payload={"my_list": [1, 2, 3, 4, 5]})
    output_message = create_and_run_component(config_yaml, message)

    # Check the output
    assert output_message.get_data("user_data.temp") == {"new_list": [3, 4, 5]}


def test_filter_transform_sub_field_greater_than_2():
    """Test the filter transform with a filter function checking for values > 2"""
    config_yaml = """
instance_name: test_instance
log:
  log_file_level: DEBUG
  log_file: solace_ai_connector.log
flows:
  - name: test_flow
    components:
      - component_name: pass_through
        component_module: pass_through
        input_transforms:
          - type: filter
            source_list_expression: input.payload:my_list
            filter_function:
              invoke:
                module: invoke_functions
                function: greater_than
                params:
                  positional:
                    - evaluate_expression(keyword_args:current_value.my_val)
                    - 2
            dest_list_expression: user_data.temp:new_list
        input_selection:
          source_expression: user_data.temp:new_list
   """
    message = Message(
        payload={
            "my_list": [{"my_val": 1}, {"my_val": 2}, {"my_val": 3}, {"my_val": 4}]
        }
    )
    output_message = create_and_run_component(config_yaml, message)

    # Check the output
    assert output_message.get_data("user_data.temp") == {
        "new_list": [{"my_val": 3}, {"my_val": 4}]
    }


def test_invoke_with_uuid_generator():
    """Verify that the uuid invoke_function returns an ID"""
    response = resolve_config_values(
        {
            "a": {
                "invoke": {"module": "invoke_functions", "function": "uuid"},
            },
        }
    )

    # Check if the output is of type string
    assert type(response["a"]) == str

    # Check if the output is a valid UUID
    assert len(response["a"]) == 36
