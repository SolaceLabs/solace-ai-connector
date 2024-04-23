"""Top level storage module for the Solace AI Event Connector. This abstracts the
actual storage implementation and provides a common interface for the rest of
the application to use."""

from abc import abstractmethod


class Storage:
    """Abstract storage class for the Solace AI Event Connector."""

    def __init__(self, config: dict):
        """Initialize the storage class."""

    @abstractmethod
    def put(self, key: str, value: dict):
        """Put a value into the storage."""

    @abstractmethod
    def get(self, key: str) -> dict:
        """Get a value from the storage."""

    @abstractmethod
    def delete(self, key: str):
        """Delete a value from the storage."""

    @abstractmethod
    def list(self) -> list:
        """List all keys in the storage."""
