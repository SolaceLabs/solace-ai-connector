# All components should inherit from this class

import threading
import queue
import traceback
import pprint

from abc import abstractmethod
from ..common.log import log
from ..common.utils import resolve_config_values
from ..common.utils import get_source_expression
from ..transforms.transforms import Transforms
from ..common.message import Message
from ..common.trace_message import TraceMessage

DEFAULT_QUEUE_TIMEOUT_MS = 200
DEFAULT_QUEUE_MAX_DEPTH = 5


class ComponentBase:
    def __init__(self, module_info, **kwargs):
        self.module_info = module_info
        self.config = kwargs.pop("config", {})
        self.index = kwargs.pop("index", None)
        self.flow_name = kwargs.pop("flow_name", None)
        self.flow_lock_manager = kwargs.pop("flow_lock_manager", None)
        self.flow_kv_store = kwargs.pop("flow_kv_store", None)
        self.stop_signal = kwargs.pop("stop_signal", None)
        self.sibling_component = kwargs.pop("sibling_component", None)
        self.component_index = kwargs.pop("component_index", None)
        self.error_queue = kwargs.pop("error_queue", None)
        self.instance_name = kwargs.pop("instance_name", None)
        self.storage_manager = kwargs.pop("storage_manager", None)
        self.trace_queue = kwargs.pop("trace_queue", False)
        self.connector = kwargs.pop("connector", None)

        self.component_config = self.config.get("component_config") or {}
        self.name = self.config.get("component_name", "<unnamed>")

        # Resolve any config items that are config modules
        resolve_config_values(self.component_config)

        self.next_component = None
        self.thread = None
        self.queue_timeout_ms = DEFAULT_QUEUE_TIMEOUT_MS
        self.need_acknowledgement = False
        self.stop_thread_event = threading.Event()
        self.current_message = None

        self.log_identifier = f"[{self.instance_name}.{self.flow_name}.{self.name}] "

        log.debug(
            "%sCreating component %s with config %s",
            self.log_identifier,
            self.name,
            self.config,
        )
        self.validate_config()
        self.setup_transforms()
        self.setup_communications()

    def create_thread_and_run(self):
        # Create a python thread for this component
        self.thread = threading.Thread(target=self.run)
        self.thread.start()
        return self.thread

    # This may be overridden by the component
    def run(self):
        while not self.stop_signal.is_set():
            message = None
            try:
                message = self.get_next_message()
                if message is not None:
                    if self.trace_queue:
                        message.trace(
                            self.trace_queue, self.log_identifier, "Received message"
                        )
                    self.process_message(message)
            except Exception as e:  # pylint: disable=broad-except
                log.error(
                    "%sComponent has crashed: %s\n%s",
                    self.log_identifier,
                    e,
                    traceback.format_exc(),
                )
                if self.error_queue:
                    user_properties = message.get_user_properties() if message else {}
                    error_message = {
                        "error": {
                            "text": str(e),
                            "exception": type(e).__name__,
                        },
                        "location": {
                            "instance": self.instance_name,
                            "flow": self.flow_name,
                            "component": self.name,
                            "component_index": self.component_index,
                        },
                    }
                    if message:
                        error_message["message"] = {
                            "payload": message.get_payload(),
                            "topic": message.get_topic(),
                            "user_properties": user_properties,
                            "user_data": message.get_user_data(),
                            "previous": message.get_previous(),
                        }
                        # Call the acknowledgements
                        message.call_acknowledgements()

                    self.error_queue.put(
                        Message(
                            payload=error_message,
                            user_properties=user_properties,
                        )
                    )

        self.stop_component()

    def get_next_message(self):
        # Get the next message from the input queue
        while not self.stop_signal.is_set():
            used_default_timeout = False
            try:
                # If the timeout is not set, then we need to use the default timeout so that
                # we can check the stop signal
                timeout = self.queue_timeout_ms
                if timeout is None:
                    timeout = self.get_default_queue_timeout()
                    used_default_timeout = True
                else:
                    log.debug(
                        "%sWaiting for message from input queue. timeout: %s, stop: %s",
                        self.log_identifier,
                        timeout,
                        self.stop_signal.is_set(),
                    )
                message = self.input_queue.get(timeout=timeout / 1000)
                log.debug(
                    "%sComponent received message %s from input queue",
                    self.log_identifier,
                    message,
                )
                self.current_message = message
                return message
            except queue.Empty:
                if not used_default_timeout:
                    self.handle_queue_timeout()
        return None

    def process_message(self, message):
        # log.debug("%sProcessing message: %s", self.log_identifier, message)

        # Do all the things we need to do before invoking the component
        data = self.process_pre_invoke(message)

        if self.trace_queue:
            self.trace_data(data)

        # Invoke the component
        result = self.invoke(message, data)

        if result is not None:
            # Do all the things we need to do after invoking the component
            # Note that there are times where we don't want to
            # send the message to the next component
            self.process_post_invoke(result, message)

    def process_pre_invoke(self, message):
        # First apply any input transforms
        self.apply_input_transforms(message)

        # Get the data that should be fed into the component
        return self.get_input_data(message)

    def process_post_invoke(self, result, message):
        # Set the previous result on the message
        message.set_previous(result)

        # If this component wants acknowledgement, add its callback
        callback = (  # pylint: disable=assignment-from-none
            self.get_acknowledgement_callback()
        )
        if callback is not None:
            message.add_acknowledgement(callback)

        # Finally send the message to the next component - or if this is the last component,
        # the component will override send_message and do whatever it needs to do with the message
        log.debug(
            "%sSending message from %s: %s", self.log_identifier, self.name, message
        )
        self.current_message = message
        self.send_message(message)

    def get_acknowledgement_callback(self):
        # This should be overridden by the component if it needs to acknowledge messages
        return None

    def get_input_data(self, message):
        component_input = self.config.get("component_input") or {
            "source_expression": "previous"
        }
        source_expression = get_source_expression(component_input)

        # This should be overridden by the component if it needs to extract data from the message
        return message.get_data(source_expression, self)

    def get_input_queue(self):
        return self.input_queue

    def apply_input_transforms(self, message):
        self.transforms.transform(message, calling_object=self)

    @abstractmethod
    def invoke(self, message, data):
        pass

    def send_message(self, message):
        if self.next_component is None:
            # This is the last component in the flow
            log.debug(
                "%sComponent %s is the last component in the flow, so not sending message",
                self.log_identifier,
                self.name,
            )
            # If there are any acknowledgements, call them
            message.call_acknowledgements()
            return
        self.next_component.enqueue(message)

    def send_to_flow(self, flow_name, message):
        if self.connector:
            self.connector.send_message_to_flow(flow_name, message)

    def enqueue(self, message):
        # Add the message to the input queue
        do_loop = True
        while not self.stop_signal.is_set() and do_loop:
            try:
                self.input_queue.put(message, timeout=1)
                do_loop = False
            except queue.Full:
                pass

    def get_config(self, key=None, default=None):
        val = self.component_config.get(key, None)
        if val is None:
            val = self.config.get(key, default)
        # If the value is callable, call it with the current message
        if callable(val):
            if self.current_message is None:
                raise ValueError(
                    f"Component {self.log_identifier} is trying to use an `invoke` config "
                    "that contains a 'source_expression()' in a context that does not "
                    "have a message available. This is likely a bug in the "
                    "component's configuration."
                )
            val = val(self.current_message)
        return val

    def resolve_callable_config(self, config, message):
        # If the value is callable, call it with the message
        # If it is a dictionary, then resolve any callable values in the dictionary (recursively)
        if isinstance(config, dict):
            for key, value in config.items():
                config[key] = self.resolve_callable_config(value, message)
        elif callable(config):
            config = config(message)
        return config

    def handle_queue_timeout(self):
        pass

    def set_next_component(self, next_component):
        self.next_component = next_component

    def get_next_component(self):
        return self.next_component

    def set_queue_timeout(self, timeout_ms):
        # Set the timeout on the input queue
        self.queue_timeout_ms = timeout_ms

    def get_default_queue_timeout(self):
        return DEFAULT_QUEUE_TIMEOUT_MS

    def get_lock(self, lock_name):
        return self.flow_lock_manager.get_lock(lock_name)

    def kv_store_get(self, key):
        return self.flow_kv_store.get(key)

    def kv_store_set(self, key, value):
        self.flow_kv_store.set(key, value)

    def setup_communications(self):
        self.queue_timeout_ms = None  # pylint: disable=assignment-from-none
        self.queue_max_depth = self.config.get(
            "component_queue_max_depth", DEFAULT_QUEUE_MAX_DEPTH
        )
        self.need_acknowledgement = False
        self.next_component = None

        # Creat an input queue for the component
        if self.sibling_component:
            # All components in the same group share the same input queue
            self.input_queue = self.sibling_component.get_input_queue()
        else:
            self.input_queue = queue.Queue(maxsize=self.queue_max_depth)

    def setup_transforms(self):
        self.transforms = Transforms(
            self.config.get("input_transforms", []), log_identifier=self.log_identifier
        )

    def validate_config(self):
        config_params = self.module_info.get("config_parameters", [])
        # Loop through the parameters and make sure they are all present if they are required
        # and set the default if it is not present
        for param in config_params:
            name = param.get("name", None)
            if name is None:
                raise ValueError(
                    f"config_parameters schema for module {self.config.get('component_module')} "
                    "does not have a name: {param}"
                )
            required = param.get("required", False)
            if required and name not in self.component_config:
                raise ValueError(
                    f"Config parameter {name} is required but not present in component {self.name}"
                )
            default = param.get("default", None)
            if default is not None and name not in self.component_config:
                self.component_config[name] = default

    def trace_data(self, data):
        # Generate a Trace object with a detailed pprint dump of the data dict
        trace_string = pprint.pformat(data, indent=4)
        self.trace_queue.put(
            TraceMessage(
                message=trace_string,
                location=self.log_identifier,
                trace_type="Component Input Data",
            )
        )

    def stop_component(self):
        # This should be overridden by the component
        pass
