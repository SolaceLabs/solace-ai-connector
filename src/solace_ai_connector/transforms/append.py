"""Append Transform - add a value to a list"""

from ..common.log import log
from .transform_base import TransformBase

info = {
    "class_name": "AppendTransform",
    "description": ("Select a source value and append it to a destination list. "),
    "config_parameters": [
        {
            "name": "source_expression",
            "description": "The field to append to the destination list.",
            "type": "string|invoke_expression",
            "required": True,
        },
        {
            "name": "dest_expression",
            "description": "The field to append the source value to.",
            "type": "string|invoke_expression",
            "required": True,
        },
    ],
}


class AppendTransform(TransformBase):

    def invoke(self, message, calling_object=None):
        # Get the source data
        source_expression = self.get_source_expression()
        source_data = message.get_data(source_expression, calling_object=calling_object)

        dest_expression = self.get_dest_expression()
        dest_list = message.get_data(dest_expression, calling_object=calling_object)
        if not dest_list:
            dest_expression = dest_expression + ".0"
            message.set_data(dest_expression, source_data)
        else:
            if isinstance(dest_list, list):
                dest_list.append(source_data)
            else:
                log.warning(
                    "Overwriting non-list data with list data.",
                )
                message.set_data(dest_expression, [source_data])
        return message
