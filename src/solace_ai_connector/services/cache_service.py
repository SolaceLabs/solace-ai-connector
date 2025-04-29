import time
import pickle
import threading
from abc import ABC, abstractmethod
from typing import Any, Optional, Dict, Tuple
from threading import Lock
from sqlalchemy import create_engine, Column, String, Float, LargeBinary
from sqlalchemy.orm import declarative_base, sessionmaker
from ..common.event import Event, EventType
from ..common.log import log


class CacheStorageBackend(ABC):

    @abstractmethod
    def get(self, key: str, include_meta=False) -> Any:
        pass

    @abstractmethod
    def set(
        self,
        key: str,
        value: Any,
        expiry: Optional[float] = None,
        metadata: Optional[Dict] = None,
    ):
        pass

    @abstractmethod
    def delete(self, key: str):
        pass

    @abstractmethod
    def get_all(self) -> Dict[str, Tuple[Any, Optional[Dict], Optional[float]]]:
        pass


class InMemoryStorage(CacheStorageBackend):

    def __init__(self):
        self.store: Dict[str, Dict[str, Any]] = {}
        self.lock = Lock()

    def get(self, key: str, include_meta=False) -> Any:
        with self.lock:
            item = self.store.get(key)
            if item is None:
                return None
            if item["expiry"] and time.time() > item["expiry"]:
                del self.store[key]
                return None
            return item if include_meta else item["value"]

    def set(
        self,
        key: str,
        value: Any,
        expiry: Optional[float] = None,
        metadata: Optional[Dict] = None,
        component=None,
    ):
        with self.lock:
            self.store[key] = {
                "value": value,
                "expiry": expiry,
                "metadata": metadata,
                "component": component,
            }

    def delete(self, key: str):
        with self.lock:
            if key in self.store:
                del self.store[key]

    def get_all(self) -> Dict[str, Tuple[Any, Optional[Dict], Optional[float], Any]]:
        with self.lock:
            return {
                key: (
                    item["value"],
                    item["metadata"],
                    item["expiry"],
                    item["component"],
                )
                for key, item in self.store.items()
            }


Base = declarative_base()


class CacheItem(Base):
    __tablename__ = "cache_items"

    key = Column(String, primary_key=True)
    value = Column(LargeBinary)
    expiry = Column(Float, nullable=True)
    item_metadata = Column(LargeBinary, nullable=True)
    component_reference = Column(String, nullable=True)


class SQLAlchemyStorage(CacheStorageBackend):

    def __init__(self, connection_string: str):
        self.engine = create_engine(connection_string)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def get(self, key: str, include_meta=False) -> Any:
        session = self.Session()
        try:
            item = session.query(CacheItem).filter_by(key=key).first()
            if item is None:
                return None
            if item.expiry and time.time() > item.expiry:
                session.delete(item)
                session.commit()
                return None
            if include_meta:
                return {
                    "value": pickle.loads(item.value),
                    "metadata": pickle.loads(item.item_metadata)
                    if item.item_metadata
                    else None,
                    "expiry": item.expiry,
                    "component": self._get_component_from_reference(
                        item.component_reference
                    ),
                }
            return pickle.loads(item.value), (
                pickle.loads(item.item_metadata) if item.item_metadata else None
            )
        finally:
            session.close()

    def set(
        self,
        key: str,
        value: Any,
        expiry: Optional[float] = None,
        metadata: Optional[Dict] = None,
        component=None,
    ):
        session = self.Session()
        try:
            item = session.query(CacheItem).filter_by(key=key).first()
            if item is None:
                item = CacheItem(key=key)
                session.add(item)
            item.value = pickle.dumps(value)
            item.expiry = time.time() + expiry if expiry else None
            item.item_metadata = pickle.dumps(metadata) if metadata else None
            item.component_reference = (
                self._get_component_reference(component) if component else None
            )
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

    def get_all(self) -> Dict[str, Tuple[Any, Optional[Dict], Optional[float], Any]]:
        session = self.Session()
        try:
            items = session.query(CacheItem).all()
            return {
                item.key: (
                    pickle.loads(item.value),
                    pickle.loads(item.item_metadata) if item.item_metadata else None,
                    item.expiry,
                    self._get_component_from_reference(item.component_reference),
                )
                for item in items
            }
        finally:
            session.close()

    def _get_component_reference(self, component):
        # This method should return a string reference to the component's location
        # For example: "flow_0.component_group_1.component_2"
        # The actual implementation will depend on how you can access this information
        # You might need to modify the component class to include this information
        return f"{component.__class__.__name__}_{id(component)}"

    def _get_component_from_reference(self, reference):
        # This method should return the actual component based on the reference
        # The actual implementation will depend on how you store and retrieve components
        # You might need to keep a global registry of components or modify the Flow class
        # to provide access to components by their reference
        return reference  # For now, we just return the reference string


class CacheService:

    def __init__(self, storage_backend: CacheStorageBackend):
        self.storage = storage_backend
        self.next_expiry = None
        self.expiry_event = threading.Event()
        self.stop_event = threading.Event()
        self.expiry_thread = threading.Thread(
            target=self._expiry_check_loop, daemon=True
        )
        self.expiry_thread.start()
        self.lock = Lock()

    def create_cache(self, name: str):
        # For in-memory storage, we don't need to do anything special
        # This method is here for future extensibility
        pass

    def add_data(
        self,
        key: str,
        value: Any,
        expiry: Optional[float] = None,
        metadata: Optional[Dict] = None,
        component=None,
    ):
        # Calculate the expiry time
        expiry = time.time() + expiry if expiry else None

        # Check if the key already exists
        cache = self.storage.get(key, include_meta=True)
        if cache:
            # Use the cache data to combine with the new data
            expiry = expiry or cache["expiry"]
            metadata = metadata or cache["metadata"]
            component = component or cache["component"]
        self.storage.set(key, value, expiry, metadata, component)
        with self.lock:
            if expiry:
                expiry_time = time.time() + expiry
                if self.next_expiry is None or expiry_time < self.next_expiry:
                    self.next_expiry = expiry_time
                    self.expiry_event.set()

    def get_data(self, key: str) -> Any:
        result = self.storage.get(key)
        return result

    def remove_data(self, key: str):
        self.storage.delete(key)

    def _expiry_check_loop(self):
        while not self.stop_event.is_set():
            if self.next_expiry is None:
                self.expiry_event.wait()
                self.expiry_event.clear()
            else:
                wait_time = max(0, self.next_expiry - time.time())
                if self.expiry_event.wait(timeout=wait_time):
                    self.expiry_event.clear()
                    continue

            self._check_expirations()

    def _check_expirations(self):
        current_time = time.time()
        expired_keys = []
        next_expiry = None

        # Use the storage backend to get all items
        all_items = self.storage.get_all()
        for key, (value, metadata, expiry, component) in all_items.items():
            if expiry and current_time > expiry:
                expired_keys.append((key, metadata, component, value))
            elif expiry and (next_expiry is None or expiry < next_expiry):
                next_expiry = expiry

        with self.lock:
            for key, _, _, _ in expired_keys:
                self.storage.delete(key)

            self.next_expiry = next_expiry

        for key, metadata, component, value in expired_keys:
            if component:
                event = Event(
                    EventType.CACHE_EXPIRY,
                    {"key": key, "metadata": metadata, "expired_data": value},
                )
                component.enqueue(event)

    def stop(self):
        self.stop_event.set()
        self.expiry_event.set()  # Wake up the expiry thread
        self.expiry_thread.join()
        log.debug("Cache service stopped")


# Factory function to create storage backend
def create_storage_backend(backend_type: str = None, **kwargs) -> CacheStorageBackend:
    if not backend_type or backend_type == "memory":
        return InMemoryStorage()
    if backend_type == "sqlalchemy":
        connection_string = kwargs.get("connection_string")
        if not connection_string:
            raise ValueError(
                "SQLAlchemy backend requires a connection_string"
            ) from None
        return SQLAlchemyStorage(connection_string)
    # Add more backend types here as needed
    raise ValueError(f"Unsupported storage backend: {backend_type}") from None
