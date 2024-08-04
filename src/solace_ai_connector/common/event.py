from enum import Enum
from typing import Any


class EventType(Enum):
    MESSAGE = "message"
    TIMER = "timer"
    # Add more event types as needed


class Event:
    def __init__(self, event_type: EventType, payload: Any):
        self.event_type = event_type
        self.payload = payload

    def __str__(self):
        return f"Event(type={self.event_type}, payload={self.payload})"
