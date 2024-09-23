from enum import Enum
from typing import Any


class EventType(Enum):
    MESSAGE = "message"
    TIMER = "timer"
    CACHE_EXPIRY = "cache_expiry"
    # Add more event types as need

    def __eq__(self, other):
        return self.value == other.value


class Event:
    def __init__(self, event_type: EventType, data: Any):
        self.event_type = event_type
        self.data = data

    def __str__(self):
        return f"Event(type={self.event_type}, data={self.data})"
