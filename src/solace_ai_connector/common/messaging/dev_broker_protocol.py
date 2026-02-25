"""Protocol definitions for the network dev broker.

This module defines the JSON-over-TCP protocol used for communication between
NetworkDevBroker clients and DevBrokerServer.

Protocol format: Newline-delimited JSON (each message is a JSON object followed by \n)
"""

import json
import re
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Literal


# Command types
CMD_CONNECT = "CONNECT"
CMD_SUBSCRIBE = "SUBSCRIBE"
CMD_UNSUBSCRIBE = "UNSUBSCRIBE"
CMD_PUBLISH = "PUBLISH"
CMD_RECEIVE = "RECEIVE"
CMD_ACK = "ACK"
CMD_DISCONNECT = "DISCONNECT"

# Response status
STATUS_OK = "OK"
STATUS_ERROR = "ERROR"
STATUS_TIMEOUT = "TIMEOUT"

# Error codes
ERR_NOT_CONNECTED = "NOT_CONNECTED"
ERR_INVALID_COMMAND = "INVALID_COMMAND"
ERR_SUBSCRIBE_FAILED = "SUBSCRIBE_FAILED"
ERR_PUBLISH_FAILED = "PUBLISH_FAILED"
ERR_INTERNAL_ERROR = "INTERNAL_ERROR"


@dataclass
class ConnectCommand:
    """Connect to the dev broker with a client ID and queue configuration."""
    cmd: str = field(default=CMD_CONNECT, init=False)
    client_id: str = ""
    queue_name: str = ""
    subscriptions: List[str] = field(default_factory=list)


@dataclass
class SubscribeCommand:
    """Subscribe to a topic pattern."""
    cmd: str = field(default=CMD_SUBSCRIBE, init=False)
    topic_pattern: str = ""


@dataclass
class UnsubscribeCommand:
    """Unsubscribe from a topic pattern."""
    cmd: str = field(default=CMD_UNSUBSCRIBE, init=False)
    topic_pattern: str = ""


@dataclass
class PublishCommand:
    """Publish a message to a topic."""
    cmd: str = field(default=CMD_PUBLISH, init=False)
    topic: str = ""
    payload: Any = None
    user_properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReceiveCommand:
    """Receive the next message from the queue with timeout."""
    cmd: str = field(default=CMD_RECEIVE, init=False)
    timeout_ms: int = 5000


@dataclass
class AckCommand:
    """Acknowledge a received message."""
    cmd: str = field(default=CMD_ACK, init=False)
    message_id: str = ""


@dataclass
class DisconnectCommand:
    """Disconnect from the dev broker."""
    cmd: str = field(default=CMD_DISCONNECT, init=False)


@dataclass
class Response:
    """Response from the server."""
    status: str = STATUS_OK
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    # Optional fields for specific responses
    client_id: Optional[str] = None
    message_id: Optional[str] = None
    message: Optional[Dict[str, Any]] = None

    @classmethod
    def ok(cls, **kwargs) -> "Response":
        """Create a successful response."""
        return cls(status=STATUS_OK, **kwargs)

    @classmethod
    def error(cls, code: str, message: str) -> "Response":
        """Create an error response."""
        return cls(status=STATUS_ERROR, error_code=code, error_message=message)

    @classmethod
    def timeout(cls) -> "Response":
        """Create a timeout response."""
        return cls(status=STATUS_TIMEOUT)


@dataclass
class BrokerMessage:
    """A message received from the broker."""
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    topic: str = ""
    payload: Any = None
    user_properties: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "message_id": self.message_id,
            "topic": self.topic,
            "payload": self.payload,
            "user_properties": self.user_properties,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BrokerMessage":
        """Create from dictionary."""
        return cls(
            message_id=data.get("message_id", str(uuid.uuid4())),
            topic=data.get("topic", ""),
            payload=data.get("payload"),
            user_properties=data.get("user_properties", {}),
        )


def encode_command(cmd) -> bytes:
    """Encode a command as JSON bytes with newline terminator."""
    return (json.dumps(asdict(cmd)) + "\n").encode("utf-8")


def encode_response(response: Response) -> bytes:
    """Encode a response as JSON bytes with newline terminator."""
    # Filter out None values
    data = {k: v for k, v in asdict(response).items() if v is not None}
    return (json.dumps(data) + "\n").encode("utf-8")


def decode_command(data: bytes) -> Dict[str, Any]:
    """Decode a JSON command from bytes."""
    return json.loads(data.decode("utf-8").strip())


def decode_response(data: bytes) -> Response:
    """Decode a JSON response from bytes."""
    d = json.loads(data.decode("utf-8").strip())
    return Response(
        status=d.get("status", STATUS_OK),
        error_code=d.get("error_code"),
        error_message=d.get("error_message"),
        client_id=d.get("client_id"),
        message_id=d.get("message_id"),
        message=d.get("message"),
    )


def subscription_to_regex(subscription: str) -> str:
    """Convert a Solace-style topic subscription to a regex pattern.

    Handles ``*`` (single-level wildcard) and ``>`` (multi-level wildcard)
    while escaping any other regex metacharacters in literal segments.
    """
    parts = subscription.split("/")
    regex_parts = []
    for part in parts:
        if part == "*":
            regex_parts.append("[^/]+")
        elif part == ">":
            regex_parts.append(".*")
        else:
            regex_parts.append(re.escape(part))
    return "/".join(regex_parts)


def topic_matches(subscription_regex: str, topic: str) -> bool:
    """Check if a topic matches a subscription regex pattern."""
    return re.match(f"^{subscription_regex}$", topic) is not None
