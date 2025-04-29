from typing import Any, Dict


class Messaging:

    def __init__(self, broker_properties: dict):
        self.broker_properties = broker_properties

    def connect(self):
        raise NotImplementedError from None

    def disconnect(self):
        raise NotImplementedError from None

    def receive_message(self, timeout_ms, queue_id: str):
        raise NotImplementedError from None

    def send_message(
        self,
        destination_name: str,
        payload: Any,
        user_properties: Dict = None,
        user_context: Dict = None,
    ):
        raise NotImplementedError from None
