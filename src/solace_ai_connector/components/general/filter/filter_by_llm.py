"""Remove any unnecessary texts before and after a json object."""

import json

from ...component_base import ComponentBase

info = {
    "class_name": "CleanJsonObject",
    "description": "Scrape javascript based websites.",
    "config_parameters": [
    ],
    "input_schema": {
        "type": "object",
        "properties": {}
    },
    "output_schema": {
        "type": "object",
        "properties": {}
    }
}

class CleanJsonObject(ComponentBase):
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)

    def invoke(self, message, data):
        text = data["text"]
        json_obj = self.extract_json(text)
        return json_obj

    # Clean a json object
    def extract_json(self, text):
        start_index = text.find('{')
        end_index = start_index
        brace_count = 0
        
        for i, char in enumerate(text[start_index:], start=start_index):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_index = i
                    break
        
        if brace_count == 0:
            json_str = text[start_index:end_index + 1]
            # If a JSON object is found, convert to JSON
            if json_str:
                try:
                    json_object = json.loads(json_str)
                    return json.dumps(json_object, indent=4)
                except json.JSONDecodeError as e:
                    raise ValueError(f"Error converting text to json: {str(e)}") from e
            else:
                return None
        else:
            return None







