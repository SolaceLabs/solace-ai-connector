"""MongoDB Agent Component for handling database search."""

from .mongo_handler import MongoHandler
from ....component_base import ComponentBase


info = {
    "class_name": "MongoDBBaseComponent",
    "description": "Base MongoDB database component",
    "config_parameters": [
        {
            "name": "database_host",
            "required": True,
            "description": "MongoDB host",
            "type": "string",
        },
        {
            "name": "database_port",
            "required": True,
            "description": "MongoDB port",
            "type": "integer",
        },
        {
            "name": "database_user",
            "required": False,
            "description": "MongoDB user",
            "type": "string",
        },
        {
            "name": "database_password",
            "required": False,
            "description": "MongoDB password",
            "type": "string",
        },
        {
            "name": "database_name",
            "required": True,
            "description": "Database name",
            "type": "string",
        },
        {
            "name": "database_collection",
            "required": False,
            "description": "Collection name - if not provided, all collections will be used",
        },
    ],
        "input_schema": {
        "type": "object",
        "properties": {
            "collection": {
                "type": "string",
                "description": "The collection to search in.",
            },
            "query": {
                "type": "object",
                "description": "The query pipeline to execute. if string is provided, it will be converted to JSON.",
            }
        },
    },
}


class MongoDBBaseComponent(ComponentBase):
    """Component for handling MongoDB database operations."""

    def __init__(self, module_info, **kwargs):
        """Initialize the MongoDB component.

        Args:
            **kwargs: Additional keyword arguments.

        Raises:
            ValueError: If required database configuration is missing.
        """
        super().__init__(module_info, **kwargs)

        # Initialize MongoDB handler
        self.db_handler = MongoHandler(
            self.get_config("database_host"),
            self.get_config("database_port"),
            self.get_config("database_user"),
            self.get_config("database_password"),
            self.get_config("database_collection"),
            self.get_config("database_name"),
        )

    def invoke(self, message, data):
        pass
