# Coordinator for performing transforms on data

from .copy import CopyTransform
from .append import AppendTransform
from .map import MapTransform
from .copy_list_item import (
    CopyListItemTransform,
)
from .reduce import ReduceTransform
from .filter import FilterTransform

name_to_class = {
    "copy": CopyTransform,
    "copy_list_item": CopyListItemTransform,
    "append": AppendTransform,
    "map": MapTransform,
    "reduce": ReduceTransform,
    "filter": FilterTransform,
}


class Transforms:

    def __init__(self, transforms, log_identifier=None):
        self.transformsList = transforms
        self.transforms = []
        self.log_identifier = log_identifier
        self.create_transforms()

    def create_transforms(self):
        if not self.transformsList:
            return
        # Loop through the transforms and create them
        for index, transform in enumerate(self.transformsList):
            self.create_transform(transform, index)

    def create_transform(self, transform, index):
        transform_type = transform.get("type", None)
        if not transform_type:
            raise ValueError(
                f"Transform at index {index} does not have a type"
            ) from None

        transform_class = name_to_class.get(transform_type, None)

        if not transform_class:
            raise ValueError(
                f"Transform at index {index} has an unknown type: {transform_type}"
            ) from None

        # Create the transform
        transform_instance = transform_class(
            transform, index, log_identifier=self.log_identifier
        )
        self.transforms.append(transform_instance)

    def transform(self, message, calling_object=None):
        # Loop through the transforms and apply them
        for transform in self.transforms:
            transform.invoke(message, calling_object=calling_object)
