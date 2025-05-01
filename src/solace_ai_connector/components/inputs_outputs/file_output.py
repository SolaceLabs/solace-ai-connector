# An output component to write to a file
import pprint

from ..component_base import ComponentBase

info = {
    "class_name": "FileOutput",
    "description": "File output component",
    "config_parameters": [],
    "input_schema": {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
            },
            "file_path": {
                "description": "The path to the file to write to",
                "type": "string",
            },
            "mode": {
                "description": "The mode to open the file in: w (write), a (append). Default is w.",
                "type": "string",
                "default": "w",
            },
        },
        "required": ["content", "file_path"],
    },
}


class FileOutput(ComponentBase):

    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)

    def invoke(self, message, data):
        content = data["content"]
        file_path = data["file_path"]
        mode = data.get("mode", "w")

        if not file_path:
            raise ValueError(
                f"file_path is required for file_output component. {self.log_identifier}"
            ) from None

        if mode not in ["w", "a"]:
            raise ValueError(
                f"mode must be either 'w' (write) or 'a' (append). {self.log_identifier}"
            ) from None

        if content:
            with open(file_path, mode, encoding="utf-8") as f:
                if isinstance(content, str):
                    f.write(content)
                else:
                    pprint.pprint(content, stream=f, width=160)

        return data
