"""Base class for broker input/output components for the Solace AI Event Connector"""

import base64
import gzip
import json
import yaml
import uuid

from abc import abstractmethod

# from solace_ai_connector.common.log import log
from ..component_base import ComponentBase
from ...common.message import Message
from ...common.messaging.messaging_builder import MessagingServiceBuilder

# TBD - at the moment, there is no connection sharing supported. It should be possible
# to share a connection between multiple components and even flows. The changes
# required are:
# 1. There is some global storage to hold all message_service objects
# 2. The message_service objects are created and stored in the global storage
# 3. The message_service objects have a reference count to know when they can be
#    disposed of
# 4. When creating a broker component, it checks the global storage for an existing
#    message_service object and uses it if it exists
# 5. When disposing of a broker component, it decrements the reference count and
#    disposes of the message_service object if the reference count is zero
# 6. The solace_messaging module needs a change to not bind to the queue as part
#    of the connect method. Instead, this class should do the queue binding. Then
#    we can skip creating the message_service object and just do an additional
#    queue binding.
# 7. This class will need to store the receiver object that is returned from the
#    queue binding and that object is used to retrieve the next message rather than
#    the message_service object.


class BrokerBase(ComponentBase):
    def __init__(self, module_info, **kwargs):
        super().__init__(module_info, **kwargs)
        self.broker_properties = self.get_broker_properties()
        self.messaging_service = (
            MessagingServiceBuilder().from_properties(self.broker_properties).build()
        )
        self.current_broker_message = None
        self.messages_to_ack = []
        self.connected = False
        self.needs_acknowledgement = True

    @abstractmethod
    def invoke(self, message, data):
        pass

    def connect(self):
        if not self.connected:
            self.messaging_service.connect()
            self.connected = True

    def disconnect(self):
        if self.connected:
            self.messaging_service.disconnect()
            self.connected = False

    def stop_component(self):
        self.disconnect()

    def decode_payload(self, payload):
        encoding = self.get_config("payload_encoding")
        payload_format = self.get_config("payload_format")
        if encoding == "base64":
            payload = base64.b64decode(payload)
        elif encoding == "gzip":
            payload = gzip.decompress(payload)
        elif encoding == "utf-8" and (
            isinstance(payload, bytes) or isinstance(payload, bytearray)
        ):
            payload = payload.decode("utf-8")
        if payload_format == "json":
            payload = json.loads(payload)
        elif payload_format == "yaml":
            payload = yaml.safe_load(payload)
        return payload

    def encode_payload(self, payload):
        encoding = self.get_config("payload_encoding")
        payload_format = self.get_config("payload_format")
        if encoding == "utf-8":
            if payload_format == "json":
                return json.dumps(payload).encode("utf-8")
            elif payload_format == "yaml":
                return yaml.dump(payload).encode("utf-8")
            else:
                return str(payload).encode("utf-8")
        elif encoding == "base64":
            if payload_format == "json":
                return base64.b64encode(json.dumps(payload).encode("utf-8"))
            elif payload_format == "yaml":
                return base64.b64encode(yaml.dump(payload).encode("utf-8"))
            else:
                return base64.b64encode(str(payload).encode("utf-8"))
        elif encoding == "gzip":
            if payload_format == "json":
                return gzip.compress(json.dumps(payload).encode("utf-8"))
            elif payload_format == "yaml":
                return gzip.compress(yaml.dump(payload).encode("utf-8"))
            else:
                return gzip.compress(str(payload).encode("utf-8"))
        else:
            if payload_format == "json":
                return json.dumps(payload)
            elif payload_format == "yaml":
                return yaml.dump(payload)
            else:
                return str(payload)

    def get_egress_topic(self, message: Message):
        pass

    def get_egress_payload(self, message: Message):
        pass

    def get_egress_user_properties(self, message: Message):
        pass

    def acknowledge_message(self, broker_message):
        pass

    def get_broker_properties(self):
        broker_properties = {
            "broker_type": self.get_config("broker_type"),
            "host": self.get_config("broker_url"),
            "username": self.get_config("broker_username"),
            "password": self.get_config("broker_password"),
            "vpn_name": self.get_config("broker_vpn"),
            "queue_name": self.get_config("broker_queue_name"),
            "subscriptions": self.get_config("broker_subscriptions"),
            "trust_store_path": self.get_config("trust_store_path"),
            "temporary_queue": self.get_config("temporary_queue"),
        }
        return broker_properties

    def get_acknowledgement_callback(self):
        pass

    def start(self):
        pass

    def generate_uuid(self):
        return str(uuid.uuid4())
