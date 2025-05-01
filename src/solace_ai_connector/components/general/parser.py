"""Parse a JSON or YAML file."""

import yaml
import json
from langchain_core.output_parsers import JsonOutputParser

from ..component_base import ComponentBase
from ...common.utils import get_obj_text


info = {
    "class_name": "Parser",
    "description": "Parse input from the given type to output type.",
    "config_parameters": [
        {
            "name": "input_format",
            "required": True,
            "description": "The input format of the data. Options: 'dict', 'json' 'yaml'. 'yaml' and 'json' must be string formatted.",
        },
        {
            "name": "output_format",
            "required": True,
            "description": "The input format of the data. Options: 'dict', 'json' 'yaml'. 'yaml' and 'json' will be string formatted.",
        },
    ],
}


class Parser(ComponentBase):

    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)

    def str_to_dict(self, text, format):
        if format == "json":
            return JsonOutputParser().invoke(text)
        elif format == "yaml":
            obj_text = get_obj_text("yaml", text)
            return yaml.safe_load(obj_text)
        else:
            return text

    def dict_to_format(self, data, format):
        if format == "json":
            return json.dumps(data, indent=4)
        elif format == "yaml":
            return yaml.dump(data)
        else:
            return data

    def invoke(self, message, data):
        input_format = self.get_config("input_format")
        output_format = self.get_config("output_format")
        if not input_format or not output_format:
            raise ValueError("Input and output format must be provided.") from None

        dict_data = data  # By default assuming it's already a dictionary
        try:
            if input_format == "json" or input_format == "yaml":
                dict_data = self.str_to_dict(data, input_format)
            elif input_format != "dict":
                raise ValueError(f"Invalid input format: {input_format}") from None
        except Exception:
            raise ValueError("Error converting input") from None

        try:
            if output_format == "json" or output_format == "yaml":
                return self.dict_to_format(dict_data, output_format)
            elif output_format == "dict":
                return dict_data
            else:
                raise ValueError(f"Invalid output format: {output_format}") from None
        except Exception:
            raise ValueError("Error converting output") from None
