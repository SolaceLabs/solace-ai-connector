"""MongoDB Agent Component for handling database search."""

import json

from .mongo_base import MongoDBBaseComponent, info as base_info

info = base_info.copy()
info["class_name"] = "MongoDBSearchComponent"
info["description"] = "Searches a MongoDB database."
info["input_schema"] = {
    "type": "object",
    "properties": {
        "collection": {
            "type": "string",
            "description": "The collection to search in.",
        },
        "query": {
            "type": "object",
            "description": "The query pipeline to execute. if string is provided, it will be converted to JSON.",
        },
    },
}


class MongoDBSearchComponent(MongoDBBaseComponent):
    """Component for handling MongoDB database operations."""

    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)

    def invoke(self, message, data):
        collection = data.get("collection")
        query = data.get("query")
        if not query:
            raise ValueError("No query provided") from None
        if isinstance(query, str):
            query = json.loads(query)
        return self.db_handler.execute_query(collection, query)
