"""Create and hold the storage handlers"""

from .storage import Storage
from .storage_file import StorageFile
from .storage_memory import StorageMemory
from .storage_s3 import StorageS3


class StorageManager:
    """Storage manager class for the Solace AI Event Connector."""

    def __init__(self, storage_config: dict):
        """Initialize the storage manager class."""
        self.storage_handlers = {}
        self.create_storage_handlers(storage_config)

    def create_storage_handlers(self, storage_configs: list):
        """Create the storage handlers"""
        for storage in storage_configs:
            storage_handler = self.create_storage_handler(storage)
            self.storage_handlers[storage["name"]] = storage_handler

    def create_storage_handler(self, storage_config: dict):
        """Create the storage handler"""
        storage_handler = self.create_storage(storage_config)
        return storage_handler

    def get_storage_handler(self, storage_name: str):
        """Get the storage handler"""
        return self.storage_handlers.get(storage_name)

    def create_storage(self, config: dict) -> "Storage":
        """Static factory method to create a storage object of the correct type."""
        storage_config = config.get("storage_config", {})
        if config["storage_type"] == "file":
            return StorageFile(storage_config)
        elif config["storage_type"] == "memory":
            return StorageMemory(storage_config)
        elif config["storage_type"] == "aws_s3":
            return StorageS3(storage_config)
        else:
            raise ValueError(f"Unsupported storage type: {config['storage_type']}")
