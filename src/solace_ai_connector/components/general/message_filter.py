"""A filtering component. This will apply a user configurable expression. If the expression
evaluates to True, the message will be passed on. If the expression evaluates to False, the
message will be discarded. If the message is discarded, any previous components that require
an acknowledgement will be acknowledged. """

from ..component_base import ComponentBase


info = {
    "class_name": "MessageFilter",
    "description": (
        "A filtering component. This will apply a user configurable expression. If the expression "
        "evaluates to True, the message will be passed on. If the expression evaluates to False, "
        "the message will be discarded. If the message is discarded, any previous components "
        "that require an acknowledgement will be acknowledged."
    ),
    "config_parameters": [
        {
            "name": "filter_expression",
            "required": True,
            "description": (
                "A dynmaic invoke configuration that will return true if message "
                "should be passed or false to drop it"
            ),
        },
    ],
    "input_schema": {
        "type": "object",
        "properties": {},
    },
    "output_schema": {
        "type": "object",
        "properties": {},
    },
}


class MessageFilter(ComponentBase):
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        self.pass_current_message = False

    def invoke(self, message, data):
        # The filter expression should be configured as a dynamic invoke value
        # which can look at the values within the message. It will be fully
        # evaluated as part of the get_config
        result = self.get_config("filter_expression")
        if not result:
            self.discard_current_message()
            return None
        return result
