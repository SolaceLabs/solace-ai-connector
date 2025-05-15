"""Class to build a Messaging Service object"""

import os

from .solace_messaging import SolaceMessaging
from .dev_broker_messaging import DevBroker


# Make a Messaging Service builder - this is a factory for Messaging Service objects
class MessagingServiceBuilder:

    def __init__(self, flow_lock_manager, flow_kv_store, broker_name, stop_signal):
        self.broker_properties = {}
        self.flow_lock_manager = flow_lock_manager
        self.flow_kv_store = flow_kv_store
        self.stop_signal = stop_signal
        self.broker_name = broker_name

    def from_properties(self, broker_properties: dict):
        self.broker_properties = broker_properties
        return self

    def build(self):
        dev_mode = self.broker_properties.get("dev_mode", os.getenv("SOLACE_DEV_MODE"))
        if (
            isinstance(dev_mode, bool)
            and dev_mode
            or dev_mode
            and isinstance(dev_mode, str)
            and dev_mode.lower() == "true"
            or self.broker_properties["broker_type"] == "dev_broker"
        ):
            return DevBroker(
                self.broker_properties, self.flow_lock_manager, self.flow_kv_store
            )
        elif (
            self.broker_properties["broker_type"] == "solace"
            or self.broker_properties["broker_type"] is None
        ):
            return SolaceMessaging(
                self.broker_properties, self.broker_name, self.stop_signal
            )

        raise ValueError(
            f"Unsupported broker type: {self.broker_properties['broker_type']}. Please either enable dev_mode or use a supported broker type."
        ) from None
