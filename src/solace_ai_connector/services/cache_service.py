import time
import pickle
import threading
from abc import ABC, abstractmethod
from typing import Any, Optional, Dict
from ..common.event import Event, EventType
from sqlalchemy import create_engine, Column, String, Float, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


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
        if item["expiry"] and time.time() > item["expiry"]:
            del self.store[key]
            return None
        return item["value"]

    def set(self, key: str, value: Any, expiry: Optional[float] = None):
        self.store[key] = {
            "value": value,
            "expiry": time.time() + expiry if expiry else None,
        }

    def delete(self, key: str):
        if key in self.store:
            del self.store[key]


Base = declarative_base()

class CacheItem(Base):
    __tablename__ = 'cache_items'

    key = Column(String, primary_key=True)
    value = Column(LargeBinary)
    expiry = Column(Float, nullable=True)

class SQLAlchemyStorage(CacheStorageBackend):
    def __init__(self, connection_string: str):
        self.engine = create_engine(connection_string)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def get(self, key: str) -> Any:
        session = self.Session()
        try:
            item = session.query(CacheItem).filter_by(key=key).first()
            if item is None:
                return None
            if item.expiry and time.time() > item.expiry:
                session.delete(item)
                session.commit()
                return None
            return pickle.loads(item.value)
        finally:
            session.close()

    def set(self, key: str, value: Any, expiry: Optional[float] = None):
        session = self.Session()
        try:
            item = session.query(CacheItem).filter_by(key=key).first()
            if item is None:
                item = CacheItem(key=key)
                session.add(item)
            item.value = pickle.dumps(value)
            item.expiry = time.time() + expiry if expiry else None
            session.commit()
        finally:
            session.close()

    def delete(self, key: str):
        session = self.Session()
        try:
            item = session.query(CacheItem).filter_by(key=key).first()
            if item:
                session.delete(item)
                session.commit()
        finally:
            session.close()


class CacheService:
    def __init__(self, storage_backend: CacheStorageBackend):
        self.storage = storage_backend
        self.expiry_callbacks = {}
        self.next_expiry = None
        self.expiry_event = threading.Event()

    def create_cache(self, name: str):
        # For in-memory storage, we don't need to do anything special
        # This method is here for future extensibility
        pass

    def add_data(
        self,
        key: str,
        value: Any,
        expiry: Optional[float] = None,
        event_data: Optional[Dict] = None,
        component=None,
    ):
        self.storage.set(key, value, expiry)
        if expiry and event_data and component:
            expiry_time = time.time() + expiry
            self.expiry_callbacks[key] = (expiry_time, event_data, component)
            if self.next_expiry is None or expiry_time < self.next_expiry:
                self.next_expiry = expiry_time
                self.expiry_event.set()

    def get_data(self, key: str) -> Any:
        return self.storage.get(key)

    def remove_data(self, key: str):
        self.storage.delete(key)
        if key in self.expiry_callbacks:
            del self.expiry_callbacks[key]

    def check_expirations(self):
        current_time = time.time()
        expired_keys = []
        next_expiry = None

        for key, (expiry_time, event_data, component) in self.expiry_callbacks.items():
            if current_time > expiry_time:
                expired_keys.append(key)
                event = Event(
                    EventType.CACHE_EXPIRY, {"key": key, "user_data": event_data}
                )
                component.enqueue(event)
            elif next_expiry is None or expiry_time < next_expiry:
                next_expiry = expiry_time

        for key in expired_keys:
            self.remove_data(key)

        self.next_expiry = next_expiry


# Factory function to create storage backend
def create_storage_backend(backend_type: str, **kwargs) -> CacheStorageBackend:
    if backend_type == "memory":
        return InMemoryStorage()
    elif backend_type == "sqlalchemy":
        connection_string = kwargs.get("connection_string")
        if not connection_string:
            raise ValueError("SQLAlchemy backend requires a connection_string")
        return SQLAlchemyStorage(connection_string)
    # Add more backend types here as needed
    raise ValueError(f"Unsupported storage backend: {backend_type}")
