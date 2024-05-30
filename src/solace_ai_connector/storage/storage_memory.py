"""Memory storage class"""

from .storage import Storage


class StorageMemory(Storage):
    """Memory storage class for the Solace AI Event Connector."""

    def __init__(self, config: dict):
        """Initialize the memory storage class."""
        self.storage = {}

    def put(self, key: str, value: str):
        """Put a value into the memory storage."""
        self.storage[key] = value

    def get(self, key: str) -> str:
        """Get a value from the memory storage."""
        return self.storage.get(key, None)

    def delete(self, key: str):
        """Delete a value from the memory storage."""
        del self.storage[key]

    def list(self) -> list:
        """List all keys in the memory storage."""
        return list(self.storage.keys())
