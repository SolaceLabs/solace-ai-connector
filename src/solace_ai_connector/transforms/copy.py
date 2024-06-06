# Copy transform

from .transform_base import TransformBase

info = {
    "class_name": "CopyTransform",
    "description": ("Copy Transform - copy a value from one field to another."),
    "config_parameters": [
        {
            "name": "source_expression",
            "description": "The field to copy from.",
            "type": "string|invoke_expression",
            "required": True,
        },
        {
            "name": "dest_expression",
            "description": "The field to copy the source value to.",
            "type": "string|invoke_expression",
            "required": True,
        },
    ],
}


class CopyTransform(TransformBase):
    def __init__(self, transform_config, index, log_identifier=None):
        super().__init__(transform_config, index, log_identifier)
        pass  # pylint: disable=unnecessary-pass
