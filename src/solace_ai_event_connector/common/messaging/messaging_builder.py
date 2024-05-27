"""Class to build a Messaging Service object"""

from .solace_messaging import SolaceMessaging


# Make a Messaging Service builder - this is a factory for Messaging Service objects
class MessagingServiceBuilder:
    def __init__(self):
        self.broker_properties = {}

    def from_properties(self, broker_properties: dict):
        self.broker_properties = broker_properties
        return self

    def build(self):
        if self.broker_properties["broker_type"] == "solace":
            print("Building Solace Messaging Service", self.broker_properties)
            return SolaceMessaging(self.broker_properties)

        raise ValueError(
            f"Unsupported broker type: {self.broker_properties['broker_type']}"
        )
