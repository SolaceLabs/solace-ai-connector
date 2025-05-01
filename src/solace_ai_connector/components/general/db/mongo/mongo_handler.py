"""MongoDB database handler for MongoDB agent."""

from pymongo import MongoClient
from typing import List, Dict, Any, Tuple
import threading

from .....common.log import log


class MongoHandler:
    """Handler for MongoDB database operations."""

    def __init__(self, host, port, user, password, collection, database_name):
        """Initialize the MongoDB handler.

        Args:
            host: MongoDB host
            port: MongoDB port
            user: MongoDB user
            password: MongoDB password
            collection: Collection name
            database_name: Database name
        """
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.collection = collection
        self.database_name = database_name
        self.local = threading.local()

    def get_connection(self):
        """Get or create a thread-local database connection."""
        if not hasattr(self.local, "client"):
            try:
                if self.user and self.password:
                    connection_string = (
                        f"mongodb://{self.user}:{self.password}@{self.host}:{self.port}"
                    )
                else:
                    connection_string = f"mongodb://{self.host}:{self.port}"

                self.local.client = MongoClient(connection_string)
                self.local.db = self.local.client[self.database_name]
                log.info("Successfully connected to MongoDB database")
            except Exception:
                log.error("Error connecting to MongoDB database")
                raise ValueError("Failed to connect to MongoDB database") from None
        return self.local.db

    def insert_documents(
        self, documents: List[Dict[str, Any]], collection: str = None
    ) -> List[str]:
        if not documents:
            return []
        if not collection:
            log.debug(
                "No collection specified, using default collection: %s", self.collection
            )
            collection = self.collection
        if not isinstance(documents, dict) and not isinstance(documents, list):
            log.error("Documents must be a dictionary or list of dictionaries")
            raise ValueError(
                "Documents must be a dictionary or list of dictionaries"
            ) from None
        if isinstance(documents, dict):
            documents = [documents]
        if not documents or not isinstance(documents[0], dict):
            log.error("Documents must be a dictionary or list of dictionaries")
            raise ValueError(
                "Documents must be a dictionary or list of dictionaries"
            ) from None
        db = self.get_connection()
        result = db[collection].insert_many(documents)
        log.debug(
            "Successfully inserted %d documents into %s",
            len(result.inserted_ids),
            collection,
        )
        return result.inserted_ids

    def execute_query(
        self, collection: str, pipeline: List[Dict]
    ) -> List[Dict[str, Any]]:
        """Execute an aggregation pipeline on MongoDB.

        Args:
            collection: Name of the collection to query
            pipeline: List of aggregation pipeline stages

        Returns:
            List of dictionaries containing the query results.

        Raises:
            Exception: If there's an error executing the pipeline.
            ValueError: If pipeline is not a valid aggregation pipeline.
        """
        if not isinstance(pipeline, list):
            raise ValueError("Pipeline must be a list of aggregation stages") from None

        # Validate each pipeline stage
        for stage in pipeline:
            if not isinstance(stage, dict) or not stage:
                log.error("Each pipeline stage must be a non-empty dictionary")
                raise ValueError(
                    "Each pipeline stage must be a non-empty dictionary"
                ) from None
            if not any(key.startswith("$") for key in stage.keys()):
                log.error(
                    "Invalid pipeline stage: %s. Each stage must start with '$'", stage
                )
                raise ValueError(
                    f"Invalid pipeline stage: {stage}. Each stage must start with '$'"
                ) from None

        try:
            db = self.get_connection()
            if not collection:
                log.debug(
                    "No collection specified, using default collection: %s",
                    self.collection,
                )
                collection = self.collection
            cursor = db[collection].aggregate(pipeline)
            result = list(cursor)
            result = self._remove_object_ids(result)
            return result
        except Exception:
            log.error("Error executing MongoDB query")
            raise ValueError("Failed to execute MongoDB query") from None

    def get_collections(self) -> List[str]:
        """Get all collection names in the database.

        Returns:
            List of collection names.
        """
        db = self.get_connection()
        return db.list_collection_names()

    def get_fields(self, collection: str) -> List[str]:
        """Get all field names for a given collection.

        Args:
            collection: Name of the collection.

        Returns:
            List of field names.
        """
        db = self.get_connection()
        # Sample a few documents to get field names
        pipeline = [
            {"$sample": {"size": 100}},
            {"$project": {"arrayofkeyvalue": {"$objectToArray": "$$ROOT"}}},
            {"$unwind": "$arrayofkeyvalue"},
            {"$group": {"_id": None, "allkeys": {"$addToSet": "$arrayofkeyvalue.k"}}},
        ]
        result = list(db[collection].aggregate(pipeline))
        if result:
            # Remove _id from fields list as it's always present
            fields = [f for f in result[0]["allkeys"] if f != "_id"]
            return sorted(fields)
        return []

    def get_sample_values(
        self, collection: str, field: str, min: int = 3, max: int = 10
    ) -> Tuple[List[str], bool]:
        """Get unique sample values for a given field in a collection. If the number of unique values is less than
        the maximum, return all unique values. Otherwise, return a random sample of unique values up to the manimum.

        Args:
            collection: Name of the collection.
            field: Name of the field.
            limit: Maximum number of unique values to return.

        Returns:
            List of unique sample values as strings,
            and a boolean indicating whether all unique values were returned.
        """
        db = self.get_connection()
        pipeline = [
            {"$match": {field: {"$exists": True}}},
            {"$group": {"_id": f"${field}"}},
            {"$sample": {"size": max + 1}},
            {"$project": {"value": "$_id", "_id": 0}},
        ]

        results = list(db[collection].aggregate(pipeline))
        if len(results) > max:
            return [str(result["value"]) for result in results[:min]], False

        return [str(result["value"]) for result in results], True

    def _remove_object_ids(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove the _id field from a list of MongoDB documents.

        Args:
            results: List of MongoDB documents.

        Returns:
            List of MongoDB documents with the _id field removed.
        """
        for result in results:
            if "_id" in result:
                del result["_id"]
        return results
