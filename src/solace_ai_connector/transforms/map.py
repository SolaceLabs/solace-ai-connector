"""This is a map transform where a list is iterated over. For each item, it is possible to
take a value from either the source list (or anywhere else in the message) and put it in the 
same index in the destination list. If the destination list is shorter than the source list, 
the destination list will be extended to match the length of the source list. """

from .transform_base import TransformBase

info = {
    "class_name": "MapTransform",
    "description": (
        "This is a map transform where a list is iterated over. For each item, it is possible to "
        "take a value from either the source list (or anywhere else in the message), optionally "
        "process it and then put it in the same index in the destination list. If the destination "
        "list is shorter than the source list, "
        "the destination list will be extended to match the length of the source list. "
        "In the processing function, you have access to the following keyword arguments:\n\n"
        " * index: The index of the current item in the source list\n"
        " * current_value: The value of the current item in the source list\n"
        " * source_list: The source list\n\n"
        "These should be accessed using `evaluate_expression(keyword_args:<value name>)`. "
        "For example, `evaluate_expression(keyword_args:current_value)`. "
        "See the example below for more detail."
    ),
    "short_description": (
        "This is a map transform where a list is iterated over, processed and then placed at the same index "
        "in the destination list."
    ),
    "config_parameters": [
        {
            "name": "source_list_expression",
            "description": "Select the list to copy from",
            "type": "string|invoke_expression",
            "required": True,
        },
        {
            "name": "source_expression",
            "description": "A field to copy. All normal source_expression options are available, allowing you to use the source list as the iterator, but copy the same value from elsewhere in the message over and over. Also, two other expression datatypes are available: 'item' and 'index'. 'item' allows you to select from the source list entry itself (e.g. item:field_name). 'index' allows you to select the index of the source list.",
            "type": "string|invoke_expression",
            "required": True,
        },
        {
            "name": "processing_function",
            "description": "An optional invoke function to process the source data before it is placed in the destination list",
            "type": "invoke_expression",
            "required": False,
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
      - type: map
        source_list_expression: input.payload:my_obj.my_list
        source_expression: item.my_val
        processing_function:
          invoke:
            module: invoke_functions
            function: add
              params:
                positional:
                  - evaluate_expression(keyword_args:current_value)
                  - 2
        dest_list_expression: user_data.output:new_list
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
        new_list: [3, 4, 5]
    }
```
""",
}


class MapTransform(TransformBase):

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
                f"{self.log_identifier}: Map transform does not have a dest list expression"
            ) from None

        # Get the processing function - pass None as the message so we get the function back
        processing_function = self.get_config(None, "processing_function")

        if processing_function and not callable(processing_function):
            raise ValueError(
                f"{self.log_identifier}: Map transform has a non-callable processing function"
            ) from None

        keyword_args = {
            "index": 0,
            "current_value": None,
            "source_list": source_list,
        }

        # Iterate over the source list
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
            if processing_function:
                try:
                    source_data = processing_function(message)
                except Exception:
                    raise ValueError(
                        f"{self.log_identifier}: Error calling processing function"
                    ) from None

            # Now put the data into the destination list
            full_dest_expression = None
            if dest_expression:
                full_dest_expression = (
                    f"{dest_list_expression}.{index}.{dest_expression}"
                )
            else:
                full_dest_expression = f"{dest_list_expression}.{index}"

            message.set_data(full_dest_expression, source_data)

        message.clear_keyword_args()
        return message
