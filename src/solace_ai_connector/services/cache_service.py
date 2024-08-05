import time
from abc import ABC, abstractmethod
from typing import Any, Optional, Dict
from ..common.event import Event, EventType

class CacheStorageBackend(ABC):
    @abstractmethod
    def get(self, key: str) -> Any:
        pass

    @abstractmethod
    def set(self, key: str, value: Any, expiry: Optional[float] = None):
        pass

    @abstractmethod
    def delete(self, key: str):
        pass

class InMemoryStorage(CacheStorageBackend):
    def __init__(self):
        self.store: Dict[str, Dict[str, Any]] = {}

    def get(self, key: str) -> Any:
        item = self.store.get(key)
        if item is None:
            return None
        if item['expiry'] and time.time() > item['expiry']:
            del self.store[key]
            return None
        return item['value']

    def set(self, key: str, value: Any, expiry: Optional[float] = None):
        self.store[key] = {
            'value': value,
            'expiry': time.time() + expiry if expiry else None
        }

    def delete(self, key: str):
        if key in self.store:
            del self.store[key]

class CacheService:
    def __init__(self, storage_backend: CacheStorageBackend):
        self.storage = storage_backend
        self.expiry_callbacks = {}

    def create_cache(self, name: str):
        # For in-memory storage, we don't need to do anything special
        # This method is here for future extensibility
        pass

    def add_data(self, key: str, value: Any, expiry: Optional[float] = None, 
                 event_data: Optional[Dict] = None, component=None):
        self.storage.set(key, value, expiry)
        if expiry and event_data and component:
            self.expiry_callbacks[key] = (time.time() + expiry, event_data, component)

    def get_data(self, key: str) -> Any:
        return self.storage.get(key)

    def remove_data(self, key: str):
        self.storage.delete(key)
        if key in self.expiry_callbacks:
            del self.expiry_callbacks[key]

    def check_expirations(self):
        current_time = time.time()
        expired_keys = []
        for key, (expiry_time, event_data, component) in self.expiry_callbacks.items():
            if current_time > expiry_time:
                expired_keys.append(key)
                event = Event(EventType.CACHE_EXPIRY, {
                    'key': key,
                    'user_data': event_data
                })
                component.enqueue(event)

        for key in expired_keys:
            self.remove_data(key)

# Factory function to create storage backend
def create_storage_backend(backend_type: str) -> CacheStorageBackend:
    if backend_type == 'memory':
        return InMemoryStorage()
    # Add more backend types here as needed
    raise ValueError(f"Unsupported storage backend: {backend_type}")
