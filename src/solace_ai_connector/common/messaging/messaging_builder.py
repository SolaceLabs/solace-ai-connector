"""Class to build a Messaging Service object"""

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
        if self.broker_properties["broker_type"] == "solace":
            return SolaceMessaging(
                self.broker_properties, self.broker_name, self.stop_signal
            )
        elif self.broker_properties["broker_type"] == "dev_broker":
            return DevBroker(
                self.broker_properties, self.flow_lock_manager, self.flow_kv_store
            )

        raise ValueError(
            f"Unsupported broker type: {self.broker_properties['broker_type']}"
        )
