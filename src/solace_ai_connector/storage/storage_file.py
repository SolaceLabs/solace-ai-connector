"""File storage implementation for the storage interface."""

import os
import json
from .storage import Storage

info = {
    "class_name": "StorageFile",
    "description": ("File storage class for the Solace AI Event Connector."),
    "config_parameters": [
        {
            "name": "file",
            "required": True,
            "description": "The file to use for storage",
            "type": "string",
        },
    ],
}


class StorageFile(Storage):
    """File storage class for the Solace AI Event Connector."""

    def __init__(self, config: dict):
        """Initialize the file storage class."""
        self.storage_file = config["file"]
        self.storage = {}
        if os.path.exists(self.storage_file):
            with open(self.storage_file, "r", encoding="utf-8") as file:
                self.storage = json.load(file)
        else:
            with open(self.storage_file, "w", encoding="utf-8") as file:
                json.dump(self.storage, file, ensure_ascii=False)

    def put(self, key: str, value: dict):
        """Put a value into the file storage as a JSON object."""
        self.storage[key] = value
        with open(self.storage_file, "w", encoding="utf-8") as file:
            json.dump(self.storage, file, ensure_ascii=False)

    def get(self, key: str) -> dict:
        """Get a value from the file storage"""
        return self.storage.get(key, None)

    def delete(self, key: str):
        """Delete a value from the file storage."""
        del self.storage[key]
        with open(self.storage_file, "w", encoding="utf-8") as file:
            json.dump(self.storage, file, ensure_ascii=False)

    def list(self) -> list:
        """List all keys in the file storage."""
        return list(self.storage.keys())
