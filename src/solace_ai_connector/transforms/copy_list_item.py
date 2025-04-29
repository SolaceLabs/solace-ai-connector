# Copy List Item transform

from .transform_base import TransformBase

# input_transforms:
#   - type: copy_list_item
#     allow_missing_source: true
#     source_expression: input.payload:chunks
#     source_property: text
#     dest_expression: user_data.temp:texts
#     dest_property:

info = {
    "class_name": "CopyListItemTransform",
    "description": (
        "Select a source list. Iterate over the list "
        "and copy the value of a field to a destination list at the "
        "same index. This can be used to create multiple lists from a "
        "single list or vice versa. NOTE: this transform is deprecated - use 'map' instead."
    ),
    "config_parameters": [
        {
            "name": "source_expression",
            "description": "Select the list to copy from",
            "type": "string|invoke_expression",
            "required": True,
        },
        {
            "name": "source_property",
            "description": "The field within that list to select",
            "type": "string|invoke_expression",
            "required": True,
        },
        {
            "name": "dest_expression",
            "description": "The list to copy the item into",
            "type": "string|invoke_expression",
            "required": True,
        },
        {
            "name": "dest_property",
            "description": "The field within the dest list to copy the item into",
            "type": "string|invoke_expression",
            "required": False,
        },
    ],
}


class CopyListItemTransform(TransformBase):

    def __init__(self, transform_config, index):
        super().__init__(transform_config, index)
        self.source_property = transform_config.get("source_property", None)
        if self.source_property is None:
            raise ValueError(
                "In CopyListItemTransform, source property not provided in transform configuration"
            ) from None
        self.dest_property = transform_config.get("dest_property", None)

    def invoke(self, message, calling_object=None):
        allow_missing_source = self.transform_config.get("allow_missing_source", False)

        # The source expression provides the list to copy from
        source_list = message.get_data(
            self.source_expression, calling_object=calling_object
        )

        if not isinstance(source_list, list):
            if allow_missing_source:
                return message
            raise ValueError(
                "In CopyListItemTransform, source expression does not resolve to a list"
            ) from None

        # Get the destination list
        dest_list = message.get_data(
            self.dest_expression, calling_object=calling_object
        )

        if dest_list is None:
            dest_list = []
            # Set the destination list back into the message
            message.set_data(self.dest_expression, dest_list)

        if not isinstance(dest_list, list):
            raise ValueError(
                "In CopyListItemTransform, destination expression does not resolve to a list"
            ) from None

        # Copy the item from the source list to the destination list
        for index, item in enumerate(source_list):
            if not isinstance(item, dict):
                raise ValueError(
                    "In CopyListItemTransform, source list item is not a dictionary"
                ) from None
            self.extend_list_if_needed(dest_list, index)
            if self.dest_property is not None:
                if dest_list[index] is None:
                    dest_list[index] = {}
                if not isinstance(dest_list[index], dict):
                    raise ValueError(
                        "In CopyListItemTransform, dest list item is not a dictionary"
                    ) from None
                dest_list[index][self.dest_property] = item[self.source_property]
            else:
                dest_list[index] = item[self.source_property]

        return message

    def extend_list_if_needed(self, list_to_extend, index):
        while len(list_to_extend) <= index:
            list_to_extend.append(None)
