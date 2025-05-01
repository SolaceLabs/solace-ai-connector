"""List filter transform"""

from .transform_base import TransformBase

info = {
    "class_name": "FilterTransform",
    "description": (
        "This is a filter transform where a list is iterated over. For each item, "
        "the provided filter_functions is run. If it evaluates to True then the item "
        "is copied to the destination list. If it evaluates to False then the item is "
        "not copied to the destination list.\n\n"
        "In the filter function, you have access to the following keyword arguments:\n\n"
        " * index: The index of the current item in the source list\n"
        " * current_value: The value of the current item in the source list\n"
        " * source_list: The source list\n\n"
        "These should be accessed using `evaluate_expression(keyword_args:<value name>)`. "
        "For example, `evaluate_expression(keyword_args:current_value)`. "
        "See the example below for more detail."
    ),
    "short_description": "Filter a list based on a filter function",
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
            "name": "filter_function",
            "description": "The invoke function to use to filter the list",
            "type": "invoke_expression",
            "required": True,
        },
        {
            "name": "dest_list_expression",
            "description": "The list to copy the item into",
            "type": "string|invoke_expression",
            "required": True,
        },
        {
            "name": "dest_expression",
            "description": "The field within the dest list to copy the item into",
            "type": "string|invoke_expression",
            "required": False,
        },
    ],
    "example_config": """
```    
    input_transforms:
      - type: filter
        source_list_expression: input.payload:my_obj.my_list
        source_expression: item
        filter_function:
          invoke:
            module: invoke_functions
            function: greater_than
              params:
                positional:
                  - evaluate_expression(keyword_args:current_value.my_val)
                  - 2
        dest_expression: user_data.output:new_list
```
This transform would take a payload like this:

```
    {
      "my_obj": {
        "my_list": [
          {"my_val": 1},
          {"my_val": 2},
          {"my_val": 3},
          {"my_val": 4}
        ],
      }
    }
```
and produce an object like this:

```
    user_data.output:
    {
        new_list: [
          {"my_val": 3},
          {"my_val": 4}
        ],
    }
```
""",
}


class FilterTransform(TransformBase):

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

        dest_list_expression = self.get_config(message, "dest_list_expression")
        dest_expression = self.get_config(message, "dest_expression", None)
        if not dest_list_expression:
            raise ValueError(
                f"{self.log_identifier}: Filter transform does not have a dest list expression"
            ) from None

        # Get the filter function - pass None as the message so we get the function back
        filter_function = self.get_config(None, "filter_function")

        if filter_function and not callable(filter_function):
            raise ValueError(
                f"{self.log_identifier}: Filter transform has a non-callable processing function"
            ) from None

        keyword_args = {
            "index": 0,
            "current_value": None,
            "source_list": source_list,
        }

        # Iterate over the source list
        dest_index = 0
        for index, source_data in enumerate(source_list):

            message.set_iteration_data(source_data, index)
            if source_expression != "item":
                source_data = message.get_data(
                    source_expression, calling_object=calling_object
                )

            keyword_args["current_value"] = source_data
            keyword_args["index"] = index
            message.set_keyword_args(keyword_args)

            # Call the accumulator function
            keep = False
            if filter_function:
                try:
                    keep = filter_function(message)
                except Exception:
                    raise ValueError(
                        f"{self.log_identifier}: Error calling processing function"
                    ) from None

            if keep:
                # Now put the data into the destination list
                full_dest_expression = None
                if dest_expression:
                    full_dest_expression = (
                        f"{dest_list_expression}.{index}.{dest_expression}"
                    )
                else:
                    full_dest_expression = f"{dest_list_expression}.{dest_index}"

                dest_index += 1
                message.set_data(full_dest_expression, source_data)

        message.clear_keyword_args()
        return message
