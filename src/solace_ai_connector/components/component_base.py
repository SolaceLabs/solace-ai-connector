import threading
import queue
import traceback
import pprint
import time
from abc import abstractmethod
from typing import Any

from ..common.log import log
from ..common.utils import resolve_config_values
from ..common.utils import get_source_expression
from ..transforms.transforms import Transforms
from ..common.message import Message
from ..common.messaging.solace_messaging import ConnectionStatus
from ..common.trace_message import TraceMessage
from ..common.event import Event, EventType
from ..flow.request_response_flow_controller import RequestResponseFlowController
from ..common.monitoring import Monitoring
from ..common.monitoring import Metrics
from ..common import Message_NACK_Outcome

DEFAULT_QUEUE_TIMEOUT_MS = 1000
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
        self.trace_queue = kwargs.pop("trace_queue", False)
        self.connector = kwargs.pop("connector", None)
        self.timer_manager = kwargs.pop("timer_manager", None)
        self.cache_service = kwargs.pop("cache_service", None)
        self.put_errors_in_error_queue = kwargs.pop("put_errors_in_error_queue", True)
        self.parent_app = kwargs.pop("app", None)

        self.component_config = self.config.get("component_config") or {}
        self.broker_request_response_config = self.config.get(
            "broker_request_response", None
        )
        self.name = self.config.get("component_name", "<unnamed>")

        resolve_config_values(self.component_config)

        self.next_component = None
        self.thread = None
        self.queue_timeout_ms = DEFAULT_QUEUE_TIMEOUT_MS
        self.need_acknowledgement = False
        self.stop_thread_event = threading.Event()
        self.current_message = None
        self.current_message_has_been_discarded = False
        self.event_message_repeat_sleep_time = 1

        self.log_identifier = f"[{self.instance_name}.{self.flow_name}.{self.name}] "

        self.validate_config()
        self.setup_transforms()
        self.setup_communications()
        self.setup_broker_request_response()

        self.monitoring = Monitoring()

    def grow_sleep_time(self):
        if self.event_message_repeat_sleep_time < 60:
            self.event_message_repeat_sleep_time *= 2

    def reset_sleep_time(self):
        self.event_message_repeat_sleep_time = 1

    def create_thread_and_run(self):
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()
        return self.thread

    def run(self):
        self.monitoring.register_callback(self.flush_metrics)
        # Start the micro monitoring thread
        monitoring_thread = threading.Thread(
            target=self.run_micro_monitoring, daemon=True
        )
        connection_status_thread = threading.Thread(
            target=self.run_connection_status_monitoring, daemon=True
        )
        monitoring_thread.start()
        connection_status_thread.start()
        # Process events until the stop signal is set
        while not self.stop_signal.is_set():
            event = None
            try:
                event = self.get_next_event()
                if event is not None:
                    self.process_event_with_tracing(event)
                self.reset_sleep_time()
            except AssertionError as e:
                try:
                    self.stop_signal.wait(timeout=self.event_message_repeat_sleep_time)
                except KeyboardInterrupt:
                    self.handle_component_error(e, event)
                self.grow_sleep_time()
                self.handle_component_error(e, event)
            except Exception as e:
                try:
                    self.stop_signal.wait(timeout=self.event_message_repeat_sleep_time)
                except KeyboardInterrupt:
                    self.handle_component_error(e, event)
                self.grow_sleep_time()
                self.handle_component_error(e, event)

        self.stop_component()
        monitoring_thread.join()
        connection_status_thread.join()

    def process_event_with_tracing(self, event):
        if self.trace_queue:
            self.trace_event(event)
        self.process_event(event)

    def handle_component_error(self, e, event):
        log.error(f"[{self.name}] {self.log_identifier} Component has crashed")
        self.handle_error(e, event)

    def get_next_event(self):
        # Check if there is a get_next_message defined by a
        # component that inherits from this class - this is
        # for backwards compatibility with older components
        sub_method = self.__class__.__dict__.get("get_next_message")

        if sub_method is not None and callable(sub_method):
            # Call the sub-classes get_next_message method and wrap it in an event
            message = self.get_next_message()  # pylint: disable=assignment-from-none
            if message is not None:
                return Event(EventType.MESSAGE, message)
            return None
        while not self.stop_signal.is_set():
            try:
                timeout = self.queue_timeout_ms or DEFAULT_QUEUE_TIMEOUT_MS
                event = self.input_queue.get(timeout=timeout / 1000)
                log.debug(
                    f"[{self.name}] {self.log_identifier} Component received event from input queue"
                )
                return event
            except queue.Empty:
                pass
        return None

    def get_next_message(self):
        return None

    def process_event(self, event):
        if event.event_type == EventType.MESSAGE:
            message = event.data
            self.current_message = message
            data = self.process_pre_invoke(message)

            if self.trace_queue:
                self.trace_data(data)

            self.current_message_has_been_discarded = False
            try:
                result = self.invoke(message, data)
            except Exception as e:
                self.current_message = None
                self.handle_negative_acknowledgements(message, e)
                raise ValueError("Error in processing message") from None
            finally:
                self.current_message = None

            if self.current_message_has_been_discarded:
                message.call_acknowledgements()
            elif result is not None:
                self.process_post_invoke(result, message)
            self.current_message = None
        elif event.event_type == EventType.TIMER:
            self.handle_timer_event(event.data)
        elif event.event_type == EventType.CACHE_EXPIRY:
            self.handle_cache_expiry_event(event.data)
        else:
            log.warning(
                f"[{self.name}] {self.log_identifier} Unknown event type: event.event_type"
            )

    def process_pre_invoke(self, message):

        self.apply_input_transforms(message)
        return self.get_input_data(message)

    def process_post_invoke(self, result, message):
        message.set_previous(result)
        callback = (  # pylint: disable=assignment-from-none
            self.get_acknowledgement_callback()
        )
        if callback is not None:
            message.add_acknowledgement(callback)

        # Finally send the message to the next component - or if this is the last component,
        # the component will override send_message and do whatever it needs to do with the message
        log.debug(
            f"[{self.name}] {self.log_identifier} Sending message from {self.name}"
        )
        self.send_message(message)

    @abstractmethod
    def invoke(self, message, data):
        pass

    def handle_timer_event(self, timer_data):
        # This method can be overridden by components that need to handle timer events
        pass

    def handle_cache_expiry_event(self, timer_data):
        # This method can be overridden by components that need to handle cache expiry events
        pass

    def discard_current_message(self):
        # If the message is to be discarded, we need to acknowledge any previous components
        self.current_message_has_been_discarded = True

    def get_acknowledgement_callback(self):
        # This should be overridden by the component if it needs to acknowledge messages
        return None

    def get_input_data(self, message):
        input_selection = (
            self.config.get("input_selection")
            or self.config.get("component_input")
            or {"source_expression": "previous"}
        )
        source_expression = get_source_expression(input_selection)

        # This should be overridden by the component if it needs to extract data from the message
        return message.get_data(source_expression, self)

    def get_input_queue(self):
        return self.input_queue

    def apply_input_transforms(self, message):
        self.transforms.transform(message, calling_object=self)

    def send_message(self, message):
        if self.next_component is None:
            # This is the last component in the flow
            message.call_acknowledgements()
            return
        event = Event(EventType.MESSAGE, message)
        self.next_component.enqueue(event)

    def send_to_flow(self, flow_name, message):
        if self.connector:
            self.connector.send_message_to_flow(flow_name, message)

    def enqueue(self, event):
        do_loop = True
        while not self.stop_signal.is_set() and do_loop:
            try:
                self.input_queue.put(event, timeout=1)
                do_loop = False
            except queue.Full:
                pass

    def get_config(self, key=None, default=None):
        # First check component config
        val = self.component_config.get(key, None)

        # If not found in component config, check app config if available
        if val is None and self.parent_app:
            val = self.parent_app.get_config(key, None)

        # If still not found, check flow config
        if val is None:
            val = self.config.get(key, default)

        # We reserve a few callable function names for internal use
        # They are used for the handler_callback component which is used
        # in testing (search the tests directory for example uses)
        if callable(val) and key not in [
            "invoke_handler",
            "get_next_event_handler",
            "send_message_handler",
        ]:
            if self.current_message is None:
                raise ValueError(
                    f"Component {self.log_identifier} is trying to use an `invoke` config "
                    "that contains a 'evaluate_expression()' in a context that does not "
                    "have a message available. This is likely a bug in the "
                    "component's configuration."
                ) from None
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

    def set_next_component(self, next_component):
        self.next_component = next_component

    def get_next_component(self):
        return self.next_component

    def get_lock(self, lock_name):
        return self.flow_lock_manager.get_lock(lock_name)

    def kv_store_get(self, key):
        return self.flow_kv_store.get(key)

    def kv_store_set(self, key, value):
        self.flow_kv_store.set(key, value)

    def setup_communications(self):
        self.queue_max_depth = self.config.get(
            "component_queue_max_depth", DEFAULT_QUEUE_MAX_DEPTH
        )
        self.need_acknowledgement = False
        self.next_component = None

        if self.sibling_component:
            self.input_queue = self.sibling_component.get_input_queue()
        else:
            self.input_queue = queue.Queue(maxsize=self.queue_max_depth)

    def setup_broker_request_response(self):
        if (
            not self.broker_request_response_config
            or not self.broker_request_response_config.get("enabled", False)
        ):
            self.broker_request_response_controller = None
            return
        broker_config = self.broker_request_response_config.get("broker_config", {})
        request_expiry_ms = self.broker_request_response_config.get(
            "request_expiry_ms", 30000
        )
        if not broker_config:
            raise ValueError(
                f"Broker request response config not found for component {self.name}"
            ) from None
        rrc_config = {
            "broker_config": broker_config,
            "request_expiry_ms": request_expiry_ms,
        }

        optional_keys = [
            "response_topic_prefix",
            "response_queue_prefix",
            "user_properties_reply_topic_key",
            "user_properties_reply_metadata_key",
            "response_topic_insertion_expression",
        ]

        for key in optional_keys:
            if key in self.broker_request_response_config:
                rrc_config[key] = self.broker_request_response_config[key]

        self.broker_request_response_controller = RequestResponseFlowController(
            config=rrc_config, connector=self.connector
        )

    def is_broker_request_response_enabled(self):
        return self.broker_request_response_controller is not None

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
                ) from None
            required = param.get("required", False)
            if required and name not in self.component_config:
                raise ValueError(
                    f"Config parameter {name} is required but not present in component {self.name}"
                ) from None
            default = param.get("default", None)
            if default is not None and name not in self.component_config:
                self.component_config[name] = default

    def trace_event(self, event):
        trace_message = TraceMessage(
            location=self.log_identifier,
            message=f"Received event: {event}",
            trace_type="Event Received",
        )
        self.trace_queue.put(trace_message)

    def trace_data(self, data):
        trace_string = pprint.pformat(data, indent=4)
        self.trace_queue.put(
            TraceMessage(
                message=trace_string,
                location=self.log_identifier,
                trace_type="Component Input Data",
            )
        )

    def handle_error(self, exception, event):
        if self.error_queue is None or not self.put_errors_in_error_queue:
            return
        error_message = {
            "error": {
                "text": str(exception),
                "exception": type(exception).__name__,
                "traceback": traceback.format_exc(),
            },
            "location": {
                "instance": self.instance_name,
                "flow": self.flow_name,
                "component": self.name,
                "component_index": self.component_index,
            },
        }
        message = None
        if event and event.event_type == EventType.MESSAGE:
            message = event.data
            if message:
                error_message["message"] = {
                    "payload": message.get_payload(),
                    "topic": message.get_topic(),
                    "user_properties": message.get_user_properties(),
                    "user_data": message.get_user_data(),
                    "previous": message.get_previous(),
                }
                message.call_acknowledgements()
            else:
                error_message["message"] = "No message available"

        self.error_queue.put(
            Event(
                EventType.MESSAGE,
                Message(
                    payload=error_message,
                    user_properties=message.get_user_properties() if message else {},
                ),
            )
        )

    def add_timer(self, delay_ms, timer_id, interval_ms=None, payload=None):
        if self.timer_manager:
            self.timer_manager.add_timer(delay_ms, self, timer_id, interval_ms, payload)

    def cancel_timer(self, timer_id):
        if self.timer_manager:
            self.timer_manager.cancel_timer(self, timer_id)

    def stop_component(self):
        # This should be overridden by the component if needed
        pass

    def cleanup(self):
        """Clean up resources used by the component"""
        log.debug(f"[{self.name}] {self.log_identifier} Cleaning up component")
        try:
            self.stop_component()
        except KeyboardInterrupt:
            pass
        if hasattr(self, "input_queue"):
            while not self.input_queue.empty():
                try:
                    self.input_queue.get_nowait()
                except queue.Empty:
                    break

    # This should be used to do an on-the-fly broker request response
    def do_broker_request_response(
        self, message, stream=False, streaming_complete_expression=None
    ):
        if self.broker_request_response_controller:
            if stream:
                return (
                    self.broker_request_response_controller.do_broker_request_response(
                        message, stream, streaming_complete_expression
                    )
                )
            else:
                generator = (
                    self.broker_request_response_controller.do_broker_request_response(
                        message
                    )
                )
                next_message, last = next(generator, None)
                return next_message
        raise ValueError(
            f"Broker request response controller not found for component {self.name}"
        ) from None

    def handle_negative_acknowledgements(self, message, exception):
        """Handle NACK for the message."""
        log.error(
            f"[{self.name}] {self.log_identifier} Component failed to process message"
        )
        nack = self.nack_reaction_to_exception(type(exception))
        message.call_negative_acknowledgements(nack)
        self.handle_error(exception, Event(EventType.MESSAGE, message))

    @abstractmethod
    def get_negative_acknowledgement_callback(self):
        """This should be overridden by the component if it needs to NACK messages."""
        return None

    @abstractmethod
    def nack_reaction_to_exception(self, exception_type):
        """This should be overridden by the component if it needs to determine
        NACK reaction regarding the exception type."""
        return Message_NACK_Outcome.REJECTED

    def get_metrics_with_header(self) -> dict[dict[Metrics, Any], Any]:
        metrics = {}
        required_metrics = self.monitoring.get_required_metrics()

        pure_metrics = self.get_metrics()
        for metric, value in pure_metrics.items():
            # filter metrics
            if metric in required_metrics:
                key = tuple(
                    [
                        ("flow", self.flow_name),
                        ("flow_index", self.index),
                        ("component", self.name),
                        ("component_module", self.config.get("component_module")),
                        ("component_index", self.component_index),
                        ("metric", metric),
                    ]
                )

                metrics[key] = value
        return metrics

    def get_metrics(self) -> dict[Metrics, Any]:
        # This method should be overridden by components that need to provide metrics.
        return {}

    def flush_metrics(self):
        # This method is intentionally left empty because not all components need to reset metrics.
        # Components that require metric reset functionality should override this method.
        pass

    def get_connection_status(self) -> ConnectionStatus:
        # This method should be overridden by components that need to provide connection status.
        # If the component does not need to provide connection status, it can leave this method empty.
        pass

    def run_connection_status_monitoring(self) -> None:
        """
        Get connection status
        """
        try:
            if self.config.get("component_module") in {"broker_input", "broker_output"}:
                while not self.stop_signal.is_set():
                    key = tuple(
                        [
                            ("flow", self.flow_name),
                            ("flow_index", self.index),
                            ("component", self.name),
                            ("component_index", self.component_index),
                        ]
                    )
                    value = self.get_connection_status()
                    self.monitoring.set_connection_status(key, value)
                    # Wait 1 second for the next interval
                    self.stop_signal.wait(timeout=1)
        except KeyboardInterrupt:
            log.info(f"[{self.name}] Monitoring connection status stopped.")

    def run_micro_monitoring(self) -> None:
        """
        Start the metric collection process in a loop.
        """
        try:
            while not self.stop_signal.is_set():
                # Collect metrics
                metrics = self.get_metrics_with_header()
                self.monitoring.collect_metrics(metrics)
                # Wait for the next interval
                sleep_interval = self.monitoring.get_interval()
                self.stop_signal.wait(timeout=sleep_interval)
                # Reset metrics in automatic mode
                if not self.monitoring.is_flush_manual():
                    self.flush_metrics()
                    log.debug(f"[{self.name}] Automatically flushed metrics.")
        except KeyboardInterrupt:
            log.info(f"[{self.name}] Monitoring stopped.")

    def get_app(self):
        """Get the app that this component belongs to"""
        return self.parent_app
