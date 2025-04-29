"""Base class for broker input/output components for the Solace AI Event Connector"""

import uuid
from typing import List

from abc import abstractmethod

from ..component_base import ComponentBase
from ...common.message import Message
from ...common.messaging.solace_messaging import ConnectionStatus
from ...common.messaging.messaging_builder import MessagingServiceBuilder
from ...common.utils import encode_payload, decode_payload

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

base_info = {
    "class_name": "BrokerBase",
    "description": "Base class for broker input/output components",
    "config_parameters": [
        {
            "name": "broker_type",
            "required": False,
            "description": "Type of broker (solace, etc.)",
            "default": "solace",
        },
        {
            "name": "dev_mode",
            "required": False,
            "description": "Operate in development mode, which just uses local queues",
            "default": "false",
        },
        {
            "name": "broker_url",
            "required": True,
            "description": "Broker URL (e.g. tcp://localhost:55555)",
        },
        {
            "name": "broker_username",
            "required": True,
            "description": "Client username for broker",
        },
        {
            "name": "broker_password",
            "required": True,
            "description": "Client password for broker",
        },
        {
            "name": "broker_vpn",
            "required": True,
            "description": "Client VPN for broker",
        },
        {
            "name": "reconnection_strategy",
            "required": False,
            "description": "Reconnection strategy for the broker (forever_retry, parametrized_retry)",
            "default": "forever_retry",
        },
        {
            "name": "retry_interval",
            "required": False,
            "description": "Reconnection retry interval in seconds for the broker",
            "default": 10000,  # in milliseconds
        },
        {
            "name": "retry_count",
            "required": False,
            "description": "Number of reconnection retries. Only used if reconnection_strategy is parametrized_retry",
            "default": 10,
        },
        {
            "name": "create_queue_on_start",
            "required": False,
            "description": "Create a queue for the broker",
            "default": True,
        },
    ],
}


class BrokerBase(ComponentBase):

    def __init__(self, module_info, **kwargs):
        super().__init__(module_info, **kwargs)
        self.broker_properties = self.get_broker_properties()
        if self.broker_properties["broker_type"] not in ["test", "test_streaming"]:
            self.messaging_service = (
                MessagingServiceBuilder(
                    self.flow_lock_manager,
                    self.flow_kv_store,
                    self.name,
                    self.stop_signal,
                )
                .from_properties(self.broker_properties)
                .build()
            )
        self.current_broker_message = None
        self.messages_to_ack = []
        self.connected = ConnectionStatus.DISCONNECTED
        self.needs_acknowledgement = True

    @abstractmethod
    def invoke(self, message, data):
        pass

    def connect(self):
        if self.connected == ConnectionStatus.DISCONNECTED:
            self.messaging_service.connect()
            self.connected = ConnectionStatus.CONNECTED

    def disconnect(self):
        if self.connected == ConnectionStatus.CONNECTED:
            self.messaging_service.disconnect()
            self.connected = ConnectionStatus.DISCONNECTED

    def stop_component(self):
        self.disconnect()

    def decode_payload(self, payload):
        encoding = self.get_config("payload_encoding")
        payload_format = self.get_config("payload_format")
        return decode_payload(payload, encoding, payload_format)

    def encode_payload(self, payload):
        encoding = self.get_config("payload_encoding")
        payload_format = self.get_config("payload_format")
        return encode_payload(payload, encoding, payload_format)

    def get_egress_topic(self, message: Message):
        pass

    def get_egress_payload(self, message: Message):
        pass

    def get_egress_user_properties(self, message: Message):
        pass

    def acknowledge_message(self, broker_message):
        pass

    def negative_acknowledge_message(self, broker_message, nack):
        pass

    def get_broker_properties(self):
        broker_properties = {
            "broker_type": self.get_config("broker_type", "solace"),
            "dev_mode": self.get_config("dev_mode"),
            "host": self.get_config("broker_url"),
            "username": self.get_config("broker_username"),
            "password": self.get_config("broker_password"),
            "vpn_name": self.get_config("broker_vpn"),
            "queue_name": self.get_config("broker_queue_name"),
            "subscriptions": self.get_config("broker_subscriptions"),
            "trust_store_path": self.get_config("trust_store_path"),
            "temporary_queue": self.get_config("temporary_queue"),
            "reconnection_strategy": self.get_config("reconnection_strategy"),
            "retry_interval": self.get_config("retry_interval"),
            "retry_count": self.get_config("retry_count"),
            "retry_interval": self.get_config("retry_interval"),
            "max_redelivery_count": self.get_config("max_redelivery_count"),
            "create_queue_on_start": self.get_config("create_queue_on_start", True),
        }
        return broker_properties

    def get_acknowledgement_callback(self):
        pass

    @abstractmethod
    def get_negative_acknowledgement_callback(self):
        """Base method for getting NACK callback"""
        return None

    def start(self):
        pass

    def generate_uuid(self):
        return str(uuid.uuid4())
