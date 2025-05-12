import time
from solace.messaging.messaging_service import MessagingService
from solace.messaging.resources.queue import Queue
from solace.messaging.receiver.persistent_message_receiver import PersistentMessageReceiver
from solace.messaging.config.message_acknowledgement_configuration import Outcome


class HowToConnectMessagingService:
    """class for reconnection strategy sampler"""

    @staticmethod
    def to_string_api_metrics(service: "MessagingService"):
        """method implies on how to get String representation of all current API metrics using
        messaging service instance

        Args:
            service: service connected instance of a messaging service, ready to be used

        """
        metrics: "ApiMetrics" = service.metrics()
        print(f"API metrics[ALL]: {metrics}\n")

    @staticmethod
    def connect_and_process_messages():
        """method to connect and process messages"""
        config = {
            "solace.messaging.transport.host": "ws://localhost:8008",
            "solace.messaging.authentication.scheme.basic.username": "default",
            "solace.messaging.authentication.scheme.basic.password": "default",
            "solace.messaging.service.vpn-name": "default",
        }
        messaging_service = MessagingService.builder().from_properties(config).build()
        try:
            messaging_service.connect()
            # HowToConnectMessagingService.to_string_api_metrics(messaging_service)
            print("Connected to Solace broker")
            queue = Queue.durable_exclusive_queue("test_queue")
            # Create receiver with required outcome support
            nacking_receiver: PersistentMessageReceiver = (
                messaging_service.create_persistent_message_receiver_builder()
                .with_required_message_outcome_support(Outcome.FAILED, Outcome.REJECTED)
                .build(queue)
            )

            # # Start the receiver and add subscription
            nacking_receiver.start()
            try:
                # Process messages for a specific duration or message count
                end_time = time.time() + 60  # Process for 60 seconds
                while time.time() < end_time:
                    # Receive with timeout (e.g., 1 second)
                    HowToConnectMessagingService.to_string_api_metrics(
                        messaging_service
                    )
                    msg = nacking_receiver.receive_message(1000)
                    HowToConnectMessagingService.to_string_api_metrics(
                        messaging_service
                    )
                    if msg:
                        print("intentionally rejected")
                        nacking_receiver.settle(msg, Outcome.REJECTED)
                    else:
                        print("No message received within timeout")
            except Exception as e:
                print(f"Error receiving message: {e}")
        except Exception as e:
            print(f"Error connecting to Solace broker: {e}")


HowToConnectMessagingService.connect_and_process_messages()
