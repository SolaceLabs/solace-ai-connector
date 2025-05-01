"""MongoDB Agent Component for handling database insert."""

import datetime
import dateutil.parser
from .mongo_base import MongoDBBaseComponent, info as base_info
from .....common.log import log

info = base_info.copy()
info["class_name"] = "MongoDBInsertComponent"
info["description"] = "Inserts data into a MongoDB database."
info["config_parameters"].extend(
    [
        {
            "name": "data_types",
            "required": False,
            "description": "Key value pairs to specify the data types for each field in the data. Used for non-JSON types like Date. Supports nested dotted names",
        },
    ]
)

POSSIBLE_TYPES = [
    "date",
    "timestamp",
    "int",
    "int32",
    "int64",
    "float",
    "double",
    "bool",
    "string",
    "null",
]


class MongoDBInsertComponent(MongoDBBaseComponent):
    """Component for handling MongoDB database operations."""

    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        self.data_types_map = self.get_config("data_types")
        if self.data_types_map:
            if not isinstance(self.data_types_map, dict):
                log.error(
                    "Invalid data types provided for MongoDB insert. Expected a dictionary. Provided: %s",
                    self.data_types_map,
                )
                raise ValueError(
                    "Invalid data types provided for MongoDB insert. Expected a dictionary."
                ) from None
            for key, field_type in self.data_types_map.items():
                if (
                    not isinstance(key, str)
                    or not isinstance(field_type, str)
                    or field_type.lower() not in POSSIBLE_TYPES
                ):
                    log.error(
                        "Invalid data types provided for MongoDB insert. Expected a dictionary with key value pairs where key is a string and value is a string from the following list: %s",
                        POSSIBLE_TYPES,
                    )
                    raise ValueError(
                        "Invalid data types provided for MongoDB insert. Expected a dictionary with key value pairs where key is a string and value is a string from the following list: "
                        + ", ".join(POSSIBLE_TYPES)
                    ) from None

    def invoke(self, message, data):
        if not data or not isinstance(data, dict) and not isinstance(data, list):
            log.error(
                "Invalid data provided for MongoDB insert. Expected a dictionary or a list of dictionary."
            )
            raise ValueError(
                "Invalid data provided for MongoDB insert. Expected a dictionary or a list of dictionary."
            ) from None

        if self.data_types_map:
            for key, field_type in self.data_types_map.items():
                if isinstance(data, list):
                    new_data = []
                    for item in data:
                        new_data.append(self._convert_data_type(item, key, field_type))
                    data = new_data
                else:
                    data = self._convert_data_type(data, key, field_type)
        return self.db_handler.insert_documents(data)

    def _convert_data_type(self, data, key, field_type):
        if not key or not field_type:
            return data
        if not isinstance(data, list) and not isinstance(data, dict):
            return data
        if "." in key:
            segments = key.split(".")
            segment = segments[0]
            if segment not in data:
                if key in data:
                    data[key] = self._convert_field_type(data[key], field_type)
                return data
            if len(segments) > 1:
                data[segment] = self._convert_data_type(
                    data[segment], ".".join(segments[1:]), field_type
                )
            else:
                data[segment] = self._convert_field_type(data[segment], field_type)
        else:
            if key in data:
                data[key] = self._convert_field_type(data[key], field_type)
        return data

    def _convert_field_type(self, value, field_type):
        field_type = field_type.lower()
        if field_type == "date" or field_type == "timestamp":
            if isinstance(value, str):
                return dateutil.parser.parse(value)
            elif isinstance(value, int) or isinstance(value, float):
                return datetime.datetime.fromtimestamp(value)
            else:
                return value
        if field_type == "int" or field_type == "int32" or field_type == "int64":
            return int(value)
        if field_type == "float" or field_type == "double":
            return float(value)
        if field_type == "bool":
            if isinstance(value, str) and value.lower() == "false":
                return False
            return bool(value)
        if field_type == "string":
            return str(value)
        if field_type == "null":
            return None
        return value
