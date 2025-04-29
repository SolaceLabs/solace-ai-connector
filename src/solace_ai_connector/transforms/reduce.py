"""List reduce transform"""

from .transform_base import TransformBase

info = {
    "class_name": "ReduceTransform",
    "description": (
        "This is a reduce transform where a list is iterated over. For each item, "
        "it is possible to take a value from either the source list (or anywhere "
        "else in the message) and accumulate it in the "
        "accumulator. The accumulated value will then be stored in the dest_expression.\n\n"
        "In the accumulator function, you have access to the following keyword arguments:\n\n"
        " * index: The index of the current item in the source list\n"
        " * accumulated_value: The current accumulated value\n"
        " * current_value: The value of the current item in the source list\n"
        " * source_list: The source list\n\n"
        "These should be accessed using `evaluate_expression(keyword_args:<value name>)`. "
        "For example, `evaluate_expression(keyword_args:current_value)`. "
        "See the example below for more detail."
    ),
    "short_description": "Reduce a list to a single value",
    "config_parameters": [
        {
            "name": "source_list_expression",
            "description": "Select the list to iterate over",
            "type": "string|invoke_expression",
            "required": True,
        },
        {
            "name": "source_expression",
            "description": "The field in the source list to accumulate",
            "type": "string|invoke_expression",
            "required": False,
        },
        {
            "name": "accumulator_function",
            "description": "The invoke expression to use to accumulate the values",
            "type": "invoke_expression",
            "required": True,
        },
        {
            "name": "initial_value",
            "description": "The initial value for the accumulator as a source_expression",
            "type": "string|invoke_expression",
            "required": True,
        },
        {
            "name": "dest_expression",
            "description": "The field to store the accumulated value",
            "type": "string|invoke_expression",
            "required": True,
        },
    ],
    "example_config": """
```    
    input_transforms:
      - type: reduce
        source_list_expression: input.payload:my_obj.my_list
        source_expression: item.my_val
        initial_value: 0
        accumulator_function:
          invoke:
            module: invoke_functions
            function: add
              params:
                positional:
                  - evaluate_expression(keyword_args:accumulated_value)
                  - evaluate_expression(keyword_args:current_value)
        dest_expression: user_data.output:my_obj.sum
```
This transform would take a payload like this:

```
    {
      "my_obj": {
        "my_list": [
          {"my_val": 1},
          {"my_val": 2},
          {"my_val": 3}
        ],
      }
    }
```
and produce an object like this:

```
    user_data.output:
    {
      "my_obj": {
        "sum": 6
      }
    }
```
    """,
}


class ReduceTransform(TransformBase):

    def __init__(self, transform_config, index, log_identifier=None):
        self.skip_expresions = True
        super().__init__(transform_config, index, log_identifier)

    def invoke(self, message, calling_object=None):
        # Get the source data
        source_list_expression = self.get_config(message, "source_list_expression")
        source_expression = self.get_source_expression(allow_none=True)
        if not source_expression:
            source_expression = "item"
        source_list = message.get_data(
            source_list_expression, calling_object=calling_object
        )

        # Get the accumulator function - pass None as the message so we get the function back
        accumulator_function = self.get_config(None, "accumulator_function")
        if not accumulator_function:
            raise ValueError(
                f"{self.log_identifier}: Reduce transform does not have an accumulator function"
            ) from None

        if not callable(accumulator_function):
            raise ValueError(
                f"{self.log_identifier}: Reduce transform has an invalid accumulator function"
            ) from None

        # Get the initial value
        initial_value = self.get_config(message, "initial_value", None)
        if initial_value:
            initial_value = message.get_data(
                initial_value, calling_object=calling_object
            )

        keyword_args = {
            "index": 0,
            "accumulated_value": initial_value,
            "current_value": None,
            "source_list": source_list,
        }

        # Loop over the source list and call the accumulator function for each item
        accumulated_value = initial_value
        for index, source_data in enumerate(source_list):
            if source_expression != "item":
                source_data = message.get_data(
                    source_expression, calling_object=calling_object
                )

            # Set the current value
            keyword_args["current_value"] = source_data
            keyword_args["index"] = index
            message.set_keyword_args(keyword_args)

            # Call the accumulator function
            try:
                accumulated_value = accumulator_function(message)
            except Exception:
                raise ValueError(
                    f"{self.log_identifier}: Error calling accumulator function"
                ) from None

            # Set the accumulated value
            keyword_args["accumulated_value"] = accumulated_value

        # Now put the data into the destination list
        dest_expression = self.get_dest_expression()
        message.set_data(dest_expression, accumulated_value)

        message.clear_keyword_args()
        return message
