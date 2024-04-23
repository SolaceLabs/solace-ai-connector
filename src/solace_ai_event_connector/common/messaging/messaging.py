# messaging.py - Base class for EDA messaging services


class Messaging:
    def __init__(self, broker_properties: dict):
        self.broker_properties = broker_properties

    def connect(self):
        raise NotImplementedError

    def disconnect(self):
        raise NotImplementedError

    def receive_message(self, timeout_ms):
        raise NotImplementedError

    # def is_connected(self):
    #     raise NotImplementedError

    # def send_message(self, destination_name: str, message: str):
    #     raise NotImplementedError

    # def subscribe(self, subscription: str, message_handler): #: MessageHandler):
    #     raise NotImplementedError
