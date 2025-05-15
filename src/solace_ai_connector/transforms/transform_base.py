# Coordinator for performing transforms on data

from ..common.utils import get_source_expression


class TransformBase:

    def __init__(self, transform_config, index, log_identifier=None):
        self.transform_config = transform_config
        self.index = index
        self.log_identifier = log_identifier
        skip = getattr(self, "skip_expresions", False)
        if not skip:
            self.source_expression = self.get_source_expression()
            self.dest_expression = self.get_dest_expression()

    # This may be overridden by the transform if more complicated
    def invoke(self, message, calling_object=None):
        # Get the source data
        source_data = message.get_data(
            self.source_expression, calling_object=calling_object
        )
        transformed_data = self.transform_data(source_data)
        message.set_data(self.dest_expression, transformed_data)
        return message

    def transform_data(self, data):
        # This should be overridden by the transform
        return data

    def get_config(self, message, key, default=None):
        value = self.transform_config.get(key, default)
        if callable(value) and message:
            return value(message)
        return value

    def get_source_expression(
        self, source_expression_key="source_expression", allow_none=False
    ):
        source_expression = get_source_expression(
            self.transform_config, source_expression_key
        )
        if not source_expression:
            if not allow_none:
                raise ValueError(
                    f"{self.log_identifier}: Transform does not have a source expression"
                ) from None
            else:
                return None
        return source_expression

    def get_dest_expression(self, dest_expression_key="dest_expression"):
        dest_expression = self.transform_config.get(dest_expression_key, None)
        if not dest_expression:
            raise ValueError(
                f"{self.log_identifier}: Transform does not have a dest expression"
            ) from None
        return dest_expression
