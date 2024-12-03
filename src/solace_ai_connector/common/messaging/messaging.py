from typing import Any, Dict


class Messaging:
    def __init__(self, broker_properties: dict):
        self.broker_properties = broker_properties

    def connect(self):
        raise NotImplementedError

    def disconnect(self):
        raise NotImplementedError

    def receive_message(self, timeout_ms, queue_id: str):
        raise NotImplementedError

    def send_message(
        self,
        destination_name: str,
        payload: Any,
        user_properties: Dict = None,
        user_context: Dict = None,
    ):
        raise NotImplementedError
