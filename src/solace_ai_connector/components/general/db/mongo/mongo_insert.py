"""MongoDB Agent Component for handling database insert."""

from .mongo_base import MongoDBBaseComponent, info as base_info

info = base_info.copy()
info["class_name"] = "MongoDBInsertComponent"
info["description"] = "Inserts data into a MongoDB database."


class MongoDBInsertComponent(MongoDBBaseComponent):
    """Component for handling MongoDB database operations."""

    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)

    def invoke(self, message, data):
        if not data:
            raise ValueError(
                "Invalid data provided for MongoDB insert. Expected a dictionary or a list of dictionary."
            )
        return self.db_handler.insert_documents(data)
