"""Session configuration for the Solace AI Connector."""

from dataclasses import dataclass, asdict, fields
from typing import Dict, Any, Optional


@dataclass
class SessionConfig:
    """
    Configuration for a request/response session.

    All configuration is stored as immutable dataclass fields.
    """

    broker_config: Dict[str, Any]
    payload_encoding: str = "utf-8"
    payload_format: str = "json"
    request_expiry_ms: int = 30000
    response_topic_prefix: str = "reply"
    response_queue_prefix: str = "reply-queue"
    max_concurrent_requests: int = 100
    user_properties_reply_topic_key: str = (
        "__solace_ai_connector_broker_request_response_topic__"
    )
    user_properties_reply_metadata_key: str = (
        "__solace_ai_connector_broker_request_reply_metadata__"
    )
    response_topic_insertion_expression: str = ""

    def __post_init__(self):
        """Validate the configuration after initialization."""
        self.validate()

    def to_controller_config(self) -> Dict[str, Any]:
        """Converts the SessionConfig to a dictionary for RequestResponseFlowController."""
        config = asdict(self)
        # The controller expects broker_config as a key within its main config dict.
        # asdict() already structures it this way.
        return config

    def validate(self) -> None:
        """Validates the session configuration."""
        if not self.broker_config or not isinstance(self.broker_config, dict):
            raise ValueError("'broker_config' must be a non-empty dictionary.")

        if self.broker_config.get("dev_mode", False):
            return

        required_keys = [
            "broker_url",
            "broker_username",
            "broker_password",
            "broker_vpn",
        ]
        for key in required_keys:
            if key not in self.broker_config:
                raise ValueError(f"'broker_config' is missing required key: {key}")

    @classmethod
    def from_dict(
        cls, config: Dict[str, Any], defaults: Optional["SessionConfig"] = None
    ) -> "SessionConfig":
        """
        Creates a SessionConfig instance from a configuration dictionary and defaults.
        """
        if defaults:
            config_dict = asdict(defaults)
        else:
            config_dict = {}

        # Deep merge broker_config
        if "broker_config" in config:
            merged_broker_config = config_dict.get("broker_config", {}).copy()
            merged_broker_config.update(config["broker_config"])
            config_dict["broker_config"] = merged_broker_config

        # Update top-level keys
        for key, value in config.items():
            if key != "broker_config":
                config_dict[key] = value

        # Filter out keys not in SessionConfig to avoid TypeError
        config_fields = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in config_dict.items() if k in config_fields}

        return cls(**filtered_data)
