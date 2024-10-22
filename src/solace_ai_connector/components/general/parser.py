"""Parse a JSON or YAML file."""
import yaml
from langchain_core.output_parsers import JsonOutputParser

from ..component_base import ComponentBase
from ...common.utils import get_obj_text


info = {
    "class_name": "Parser",
    "description": "Parse a JSON string and extract data fields.",
    "config_parameters": [
        {
            "name": "input_format",
            "required": True,
            "description": "The input format of the data. Options: 'json', 'yaml'.",
        },
    ],
}

class Parser(ComponentBase):
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)

    def invoke(self, message, data):
        text = data["text"]
        res_format = self.get_config("input_format", "json")
        if res_format == "json":
            try:
                parser = JsonOutputParser()
                json_res = parser.invoke(text)
                return json_res
            except Exception as e:
                raise ValueError(f"Error parsing the input JSON: {str(e)}") from e
        elif res_format == "yaml":
            obj_text = get_obj_text("yaml", text)
            try:
                yaml_res = yaml.safe_load(obj_text)
                return yaml_res
            except Exception as e:
                raise ValueError(f"Error parsing the input YAML: {str(e)}") from e
        else:
            return text
