"""This component has an empty processing stage by default. The user config can use 
'invoke' configuration to create the processing stage at configuration time. 
The 'invoke' configuration will be executed at runtime, once per message"""

from ..component_base import ComponentBase


info = {
    "class_name": "UserProcessor",
    "description": (
        "A component that allows the processing stage to be defined in the "
        "configuration file using 'invoke' statements. The configuration "
        "must be specified with the 'component_processing:' property alongside the "
        "'component_module:' property in the component's configuration. The input "
        "and output schemas are free-form. The user-defined processing must line up with the input "
    ),
    "short_description": (
        "A component that allows the processing stage to be "
        "defined in the configuration file."
    ),
    "config_parameters": [],
    "input_schema": {
        "type": "object",
        "properties": {},
    },
    "output_schema": {
        "type": "object",
        "properties": {},
    },
}


class UserProcessor(ComponentBase):
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)

    def invoke(self, message, data):
        message.set_invoke_data(data)
        component_processing = self.get_config("component_processing")
        if component_processing and callable(component_processing):
            return component_processing(message)
        return component_processing
