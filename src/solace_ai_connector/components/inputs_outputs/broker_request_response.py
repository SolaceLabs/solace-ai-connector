"""Request-Response broker component for the Solace AI Event Connector"""

import threading
import uuid
import json
import queue
from copy import deepcopy

from ...common.log import log
from ...common.utils import set_data_value, get_data_value, remove_data_value
from .broker_base import BrokerBase
from ...common.message import Message
from ...common.utils import ensure_slash_on_end, ensure_slash_on_start


info = {
    "class_name": "BrokerRequestResponse",
    "description": (
        "This component sends request messages to a broker and waits for correlated responses, "
        "handling both outbound requests and inbound responses within a single component. "
        "This is performed asynchronously, allowing to to handle multiple requests and responses "
        "at the same time. "
    ),
    "config_parameters": [
        {
            "name": "broker_type",
            "required": False,
            "description": "Type of broker (Solace, MQTT, etc.)",
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
            "name": "payload_encoding",
            "required": False,
            "description": "Encoding for the payload (utf-8, base64, gzip, none)",
            "default": "utf-8",
        },
        {
            "name": "payload_format",
            "required": False,
            "description": "Format for the payload (json, yaml, text)",
            "default": "json",
        },
        {
            "name": "response_topic_prefix",
            "required": False,
            "description": "Prefix for reply topics",
            "default": "reply",
        },
        {
            "name": "response_topic_suffix",
            "required": False,
            "description": "Suffix for reply topics",
            "default": "",
        },
        {
            "name": "response_topic_insertion_expression",
            "required": False,
            "description": (
                "Expression to insert the reply topic into the "
                "request message. "
                "If not set, the reply topic will only be added to the "
                "request_response_metadata. The expression uses the "
                "same format as other data expressions: "
                "(e.g input.payload:myObj.replyTopic). "
                "If there is no object type in the expression, "
                "it will default to 'input.payload'."
            ),
            "default": "",
        },
        {
            "name": "response_queue_prefix",
            "required": False,
            "description": "Prefix for reply queues",
            "default": "reply-queue",
        },
        {
            "name": "user_properties_reply_topic_key",
            "required": False,
            "description": "Key to store the reply topic in the user properties. Start with : for nested object",
            "default": "__solace_ai_connector_broker_request_response_topic__",
        },
        {
            "name": "user_properties_reply_metadata_key",
            "required": False,
            "description": "Key to store the reply metadata in the user properties. Start with : for nested object",
            "default": "__solace_ai_connector_broker_request_reply_metadata__",
        },
        {
            "name": "request_expiry_ms",
            "required": False,
            "description": "Expiry time for cached requests in milliseconds",
            "default": 60000,
            "type": "integer",
        },
        {
            "name": "streaming",
            "required": False,
            "description": "The response will arrive in multiple pieces. If True, "
            "the streaming_complete_expression must be set and will be used to "
            "determine when the last piece has arrived.",
        },
        {
            "name": "streaming_complete_expression",
            "required": False,
            "description": "The source expression to determine when the last piece of a "
            "streaming response has arrived.",
        },
        {
            "name": "streaming",
            "required": False,
            "description": "The response will arrive in multiple pieces. If True, "
            "the streaming_complete_expression must be set and will be used to "
            "determine when the last piece has arrived.",
        },
        {
            "name": "streaming_complete_expression",
            "required": False,
            "description": "The source expression to determine when the last piece of a "
            "streaming response has arrived.",
        },
        {
            "name": "streaming",
            "required": False,
            "description": "The response will arrive in multiple pieces. If True, "
            "the streaming_complete_expression must be set and will be used to "
            "determine when the last piece has arrived.",
        },
        {
            "name": "streaming_complete_expression",
            "required": False,
            "description": "The source expression to determine when the last piece of a "
            "streaming response has arrived.",
        },
    ],
    "input_schema": {
        "type": "object",
        "properties": {
            "payload": {
                "type": "any",
                "description": "Payload of the request message to be sent to the broker",
            },
            "topic": {
                "type": "string",
                "description": "Topic to send the request message to",
            },
            "user_properties": {
                "type": "object",
                "description": "User properties to send with the request message",
            },
            "response_topic_suffix": {
                "type": "string",
                "description": "Suffix for the reply topic",
            },
            "stream": {
                "type": "boolean",
                "description": "Whether this will have a streaming response",
                "default": False,
            },
            "streaming_complete_expression": {
                "type": "string",
                "description": "Expression to determine when the last piece of a "
                "streaming response has arrived. Required if stream is True.",
            },
        },
        "required": ["payload", "topic"],
    },
    "output_schema": {
        "type": "object",
        "properties": {
            "request": {
                "type": "object",
                "properties": {
                    "payload": {"type": "any"},
                    "topic": {"type": "string"},
                    "user_properties": {"type": "object"},
                },
            },
            "response": {
                "type": "object",
                "properties": {
                    "payload": {"type": "any"},
                    "topic": {"type": "string"},
                    "user_properties": {"type": "object"},
                },
            },
        },
        "required": ["request", "response"],
    },
}

DEFAULT_REPLY_TOPIC_KEY = "__solace_ai_connector_broker_request_response_topic__"
DEFAULT_REPLY_METADATA_KEY = "__solace_ai_connector_broker_request_reply_metadata__"


class BrokerRequestResponse(BrokerBase):
    """Request-Response broker component for the Solace AI Event Connector"""

    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        self._local_stop_signal = threading.Event()
        self.need_acknowledgement = False
        self.request_expiry_ms = self.get_config("request_expiry_ms")
        self.response_topic_prefix = ensure_slash_on_end(
            self.get_config("response_topic_prefix")
        )
        self.response_topic_suffix = ensure_slash_on_start(
            self.get_config("response_topic_suffix")
        )
        self.response_queue_prefix = ensure_slash_on_end(
            self.get_config("response_queue_prefix")
        )
        self.user_properties_reply_topic_key = self.get_config(
            "user_properties_reply_topic_key", DEFAULT_REPLY_TOPIC_KEY
        )
        self.user_properties_reply_metadata_key = self.get_config(
            "user_properties_reply_metadata_key", DEFAULT_REPLY_METADATA_KEY
        )
        self.requestor_id = str(uuid.uuid4())
        self.reply_queue_name = f"{self.response_queue_prefix}{self.requestor_id}"
        self.response_topic = f"{self.response_topic_prefix}{self.requestor_id}{self.response_topic_suffix}"
        self.response_thread = None
        self.streaming = self.get_config("streaming")
        self.streaming_complete_expression = self.get_config(
            "streaming_complete_expression"
        )
        self.broker_type = self.broker_properties.get("broker_type", "solace")
        if self.broker_type in ["test", "test_streaming", "test_bad_payload"]:
            self.test_mode = True
        else:
            self.test_mode = False
        self.broker_properties["temporary_queue"] = True
        self.broker_properties["queue_name"] = self.reply_queue_name
        self.broker_properties["subscriptions"] = [
            {
                "topic": self.response_topic,
                "qos": 1,
            },
            {
                "topic": self.response_topic + "/>",
                "qos": 1,
            },
        ]

        self.response_topic_insertion_expression = self.get_config(
            "response_topic_insertion_expression"
        )
        if self.response_topic_insertion_expression:
            if ":" not in self.response_topic_insertion_expression:
                self.response_topic_insertion_expression = (
                    f"input.payload:{self.response_topic_insertion_expression}"
                )

        if self.test_mode:
            self.setup_test_pass_through()
        else:
            self.connect()

        self.start()

    def start(self):
        # Will get called after the message service is connected
        self.start_response_thread()

    def setup_reply_queue(self):
        self.messaging_service.bind_to_queue(
            self.reply_queue_name, [self.response_topic], temporary=True
        )

    def setup_test_pass_through(self):
        self.pass_through_queue = queue.Queue()

    def start_response_thread(self):
        if self.test_mode:
            self.response_thread = threading.Thread(
                target=self.handle_test_pass_through, daemon=True
            )
        else:
            self.response_thread = threading.Thread(
                target=self.handle_responses, daemon=True
            )
        self.response_thread.start()

    def handle_responses(self):
        while not self._local_stop_signal.is_set():
            try:
                broker_message = self.messaging_service.receive_message(
                    1000, self.reply_queue_name
                )
                if broker_message:
                    self.process_response(broker_message)
            except Exception as e:
                log.error("Error handling response.", trace=e)

    def handle_test_pass_through(self):
        while not self._local_stop_signal.is_set():
            try:
                message = self.pass_through_queue.get(timeout=1)
                self.process_response(message)
            except queue.Empty as e:
                log.debug("No messages in pass-through queue.", trace=e)
                continue
            except Exception as e:
                log.error("Error handling test passthrough.", trace=e)

    def process_response(self, broker_message):
        try:
            if self.test_mode:
                payload = broker_message.get_payload()
                topic = broker_message.get_topic()
                user_properties = broker_message.get_user_properties()
            else:
                payload = broker_message.get("payload")
                topic = broker_message.get("topic")
                user_properties = broker_message.get("user_properties", {})

            try:
                payload = self.decode_payload(payload)
            except ValueError as e:
                log.error(
                    "Error decoding payload in request/response: %s", e, exc_info=True
                )
                payload = {
                    "error": "Payload decode error",
                    "details": str(e),
                }

            if not user_properties:
                log.error("Received response without user properties.")
                return

            streaming_complete_expression = None
            metadata_json = get_data_value(
                user_properties, self.user_properties_reply_metadata_key, True
            )
            if not metadata_json:
                log.error("Received response without metadata.")
                return

            try:
                metadata_stack = json.loads(metadata_json)
            except json.JSONDecodeError as e:
                log.error("Received response with invalid metadata JSON.", trace=e)
                return

            if not metadata_stack:
                log.error("Received response with empty metadata stack.")
                return

            try:
                current_metadata = metadata_stack.pop()
            except IndexError as e:
                log.error("Received response with invalid metadata stack.", trace=e)
                return
            request_id = current_metadata.get("request_id")
            if not request_id:
                log.error("Received response without request_id in metadata.")
                return

            cached_request = self.cache_service.get_data(request_id)
            if not cached_request:
                log.error("Received response for unknown request_id.")
                return

            stream = cached_request.get("stream", False)
            streaming_complete_expression = cached_request.get(
                "streaming_complete_expression"
            )

            response = {
                "payload": payload,
                "topic": topic,
                "user_properties": user_properties,
            }

            # Update the metadata in the response
            if metadata_stack:
                set_data_value(
                    response["user_properties"],
                    self.user_properties_reply_metadata_key,
                    json.dumps(metadata_stack),
                )
                # Put the last reply topic back in the user properties
                set_data_value(
                    response["user_properties"],
                    self.user_properties_reply_topic_key,
                    metadata_stack[-1]["response_topic"],
                )
            else:
                # Remove the metadata and reply topic from the user properties
                remove_data_value(
                    response["user_properties"], self.user_properties_reply_metadata_key
                )
                remove_data_value(
                    response["user_properties"], self.user_properties_reply_topic_key
                )

            message = Message(
                payload=payload,
                user_properties=user_properties,
                topic=topic,
            )
            self.process_post_invoke(response, message)

            # Only remove the cache entry if this isn't a streaming response or
            # if it is the last piece of a streaming response
            last_piece = True
            if stream and streaming_complete_expression:
                is_last = message.get_data(streaming_complete_expression)
                if not is_last:
                    last_piece = False
                    self.cache_service.add_data(
                        key=request_id,
                        value=cached_request,
                        expiry=self.request_expiry_ms / 1000,  # Reset expiry time
                        component=self,
                    )

            if last_piece:
                self.cache_service.remove_data(request_id)
        finally:
            if not self.test_mode:
                self.messaging_service.ack_message(broker_message)

    def invoke(self, message, data):
        request_id = str(uuid.uuid4())

        if "user_properties" not in data:
            data["user_properties"] = {}

        stream = False
        if "stream" in data:
            stream = data["stream"]
        streaming_complete_expression = None
        if "streaming_complete_expression" in data:
            streaming_complete_expression = data["streaming_complete_expression"]

        topic = self.response_topic
        if "response_topic_suffix" in data:
            topic = f"{topic}/{data['response_topic_suffix']}"

        metadata = {"request_id": request_id, "response_topic": topic}

        existing_metadata_json = get_data_value(
            data["user_properties"], self.user_properties_reply_metadata_key, True
        )
        if existing_metadata_json:
            try:
                existing_metadata = json.loads(existing_metadata_json)
                if isinstance(existing_metadata, list):
                    existing_metadata.append(metadata)
                    metadata = existing_metadata
                else:
                    log.warning("Invalid existing metadata format.")
            except json.JSONDecodeError:
                log.warning("Failed to decode existing metadata JSON.")
        else:
            metadata = [metadata]

        set_data_value(
            data["user_properties"],
            self.user_properties_reply_metadata_key,
            json.dumps(metadata),
        )
        set_data_value(
            data["user_properties"], self.user_properties_reply_topic_key, topic
        )

        # If we are configured to also insert the response topic into the request message
        # then create a temporary message to do so
        if self.response_topic_insertion_expression:
            tmp_message = Message(
                payload=data["payload"],
                user_properties=data["user_properties"],
                topic=data["topic"],
            )
            tmp_message.set_data(
                self.response_topic_insertion_expression, self.response_topic
            )
            data["payload"] = tmp_message.get_payload()
            data["user_properties"] = tmp_message.get_user_properties()

        if self.test_mode:
            if self.broker_type == "test_streaming":
                # The payload should be an array. Send one message per item in the array
                if not isinstance(data["payload"], list):
                    raise ValueError(
                        "Payload must be a list for test_streaming broker"
                    ) from None
                for item in data["payload"]:
                    encoded_payload = self.encode_payload(item)
                    self.pass_through_queue.put(
                        Message(
                            payload=encoded_payload,
                            user_properties=deepcopy(data["user_properties"]),
                            topic=data["topic"],
                        )
                    )
            else:
                encoded_payload = self.encode_payload(data["payload"])
                self.pass_through_queue.put(
                    Message(
                        payload=encoded_payload,
                        user_properties=data["user_properties"],
                        topic=data["topic"],
                    )
                )
        else:
            encoded_payload = self.encode_payload(data["payload"])
            self.messaging_service.send_message(
                destination_name=data["topic"],
                payload=encoded_payload,
                user_properties=data["user_properties"],
            )

        data["stream"] = stream
        data["streaming_complete_expression"] = streaming_complete_expression

        self.cache_service.add_data(
            key=request_id,
            value=data,
            expiry=self.request_expiry_ms / 1000,  # Convert to seconds
            component=self,
        )

        return None  # The actual result will be processed in handle_responses

    def stop_component(self):
        if self.response_thread:
            self._local_stop_signal.set()
            self.response_thread.join()
        super().stop_component()

    def get_metrics(self):
        # override because it removes messaging_service from the BrokerBase
        return {}
