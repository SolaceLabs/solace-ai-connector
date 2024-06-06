"""Simple memory tester component"""

from ...component_base import ComponentBase


info = {
    "class_name": "MemoryTester",
    "description": ("A component that will exchange a value from the memory storage"),
    "config_parameters": [
        {
            "name": "storage_name",
            "required": True,
            "description": "The name of the storage to use",
            "type": "string",
        },
    ],
    "input_schema": {
        "type": "object",
        "properties": {
            "test_value": {
                "type": "string",
                "description": "The value to store in the memory storage",
            },
        },
        "required": ["test_value"],
    },
    "output_schema": {
        "type": "object",
        "properties": {},
    },
}


class MemoryTester(ComponentBase):
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)

    def invoke(self, message, data):
        storage = self.storage_manager.get_storage_handler(
            self.get_config("storage_name")
        )
        storage_data = storage.get("test")

        if storage_data is None:
            storage_data = {"test": "initial_value"}

        old_value = storage_data.get("test")
        new_value = data.get("test_value")

        storage.put("test", {"test": new_value})
        return {"test_value": old_value}
