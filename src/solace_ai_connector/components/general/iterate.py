"""Iterate over a list of items and output each one as a separate message"""

from ..component_base import ComponentBase
from ...common.message import Message

info = {
    "class_name": "Iterate",
    "description": (
        "Take a single message that is a list and "
        "output each item in that list as a separate message"
    ),
    "config_parameters": [],
    "input_schema": {
        "type": "array",
        "items": {
            "type": "object",
        },
    },
    "output_schema": {
        "type": "object",
        "properties": {},
    },
    "example_config": """
```yaml
   - component_name: iterate_example
     component_module: iterate
     component_config: 
     input_selection:
       # Take the list field from the message and use it as the input to the iterator
       source_expression: input.payload:embeddings
```
""",
}


class Iterate(ComponentBase):

    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)

    def invoke(self, message, data):
        # data is the list of items
        # Loop over them and output each one as a separate message
        if not isinstance(data, list):
            raise ValueError(
                "The iterate component requires the input to be a list"
            ) from None

        for item in data:
            # Create a new message for each item unless it is the last item
            # in which case we reuse the existing message
            if item != data[-1]:
                topic = message.get_topic()
                user_properties = message.get_user_properties()
                new_message = Message(
                    payload=item, topic=topic, user_properties=user_properties
                )
            else:
                new_message = message

            # Send the message
            self.process_post_invoke(item, new_message)
