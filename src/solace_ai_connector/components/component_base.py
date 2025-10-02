import logging
import threading
import queue
import traceback
import pprint
import asyncio
from abc import abstractmethod
from typing import Any, Optional, Dict, List

from ..common.utils import resolve_config_values
from ..common.utils import get_source_expression
from ..transforms.transforms import Transforms
from ..common.message import Message
from ..common.messaging.solace_messaging import ConnectionStatus
from ..common.trace_message import TraceMessage
from ..common.event import Event, EventType
from ..flow.request_response_flow_controller import RequestResponseFlowController
from ..flow.multi_session_request_response_manager import (
    MultiSessionRequestResponseManager,
)
from ..common.session_config import SessionConfig
from ..common.monitoring import Monitoring
from ..common.monitoring import Metrics
from ..common import Message_NACK_Outcome
from ..common.config_validation import validate_config_block

log = logging.getLogger(__name__)

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
        self._component_rrc = None  # Initialize component-level RRC attribute
        self._multi_session_manager = None

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

        self.log_identifier = f"[{self.instance_name}.{self.flow_name}.{self.name}] "

        self.validate_config()
        self._setup_transforms()
        self._setup_communications()
        self._setup_component_broker_request_response()
        self._setup_multi_session_request_response()

        self.monitoring = Monitoring()

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
            except AssertionError as e:
                self.handle_component_error(e, event)
            except Exception as e:
                self.handle_component_error(e, event)

        self.stop_component()
        monitoring_thread.join()
        connection_status_thread.join()

    def process_event_with_tracing(self, event):
        if self.trace_queue:
            self.trace_event(event)
        self.process_event(event)

    def handle_component_error(self, e, event):
        log.error(
            "[%s] %s Component has crashed",
            self.name,
            self.log_identifier,
        )
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
                    "[%s] %s Component received event from input queue",
                    self.name,
                    self.log_identifier,
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
                "[%s] %s Unknown event type: %s",
                self.name,
                self.log_identifier,
                event.event_type,
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
            "[%s] %s Sending message from %s",
            self.name,
            self.log_identifier,
            self.name,
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
        # First check component_config (specific config for this component instance)
        val = self.component_config.get(key, None)

        # If not found in component_config, check app config if available
        if val is None and self.parent_app:
            val = self.parent_app.get_config(key, None)

        # If still not found, check self.config (component entry from flow/app config)
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

    def _setup_communications(self):
        self.queue_max_depth = self.config.get(
            "component_queue_max_depth", DEFAULT_QUEUE_MAX_DEPTH
        )
        self.need_acknowledgement = False
        self.next_component = None

        if self.sibling_component:
            self.input_queue = self.sibling_component.get_input_queue()
        else:
            self.input_queue = queue.Queue(maxsize=self.queue_max_depth)

    def _setup_component_broker_request_response(self):
        """Initializes RRC if configured at the component level (backward compatibility)."""
        if (
            self.broker_request_response_config
            and self.broker_request_response_config.get("enabled", False)
        ):
            log.warning(
                "[%s] %s Using deprecated component-level 'broker_request_response' config. "
                "Consider migrating to app-level 'request_reply_enabled' in the 'broker' config.",
                self.name,
                self.log_identifier,
            )
            broker_config = self.broker_request_response_config.get("broker_config", {})
            request_expiry_ms = self.broker_request_response_config.get(
                "request_expiry_ms", 30000  # Default from old logic
            )
            if not broker_config:
                raise ValueError(
                    f"Component-level broker_request_response config missing 'broker_config' for component {self.name}"
                ) from None

            # Construct config for the controller, extracting relevant keys
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

            try:
                # Store the controller instance on the component
                self._component_rrc = RequestResponseFlowController(
                    config=rrc_config, connector=self.connector
                )
                log.info(
                    "[%s] %s Initialized component-level RequestResponseFlowController.",
                    self.name,
                    self.log_identifier,
                )
            except Exception:
                log.exception(
                    f"[{self.name}] {self.log_identifier} Failed to initialize component-level RRC"
                )
                # Decide if this should be fatal
                raise ValueError("Failed to initialize component-level RRC") from None
        else:
            self._component_rrc = None

    def _setup_multi_session_request_response(self):
        """Initializes the multi-session request/response manager if configured."""
        multi_session_config = self.get_config("multi_session_request_response")
        if multi_session_config and multi_session_config.get("enabled", False):
            log.info(
                "[%s] %s Multi-session request/response is enabled.",
                self.name,
                self.log_identifier,
            )

            # Try to get explicit default_broker_config first
            default_broker_config = multi_session_config.get(
                "default_broker_config", {}
            )

            # If not found, try to inherit from the parent app's broker config
            if not default_broker_config and self.parent_app:
                log.debug(
                    "[%s] %s No explicit default_broker_config found, attempting to inherit from app's broker config.",
                    self.name,
                    self.log_identifier,
                )
                app_broker_config = self.parent_app.app_info.get("broker")
                if app_broker_config:
                    default_broker_config = app_broker_config
                    log.info(
                        "[%s] %s Using parent app's broker configuration as default for multi-session request/response.",
                        self.name,
                        self.log_identifier,
                    )

            # A default broker config is optional. If not provided, each session
            # must be created with a full 'broker_config' override.
            default_session_config = None
            if default_broker_config:
                try:
                    default_session_config = SessionConfig(
                        broker_config=default_broker_config
                    )
                except ValueError as e:
                    raise ValueError(
                        f"Invalid 'default_broker_config' for multi_session_request_response: {e}"
                    ) from e
            else:
                log.info(
                    "[%s] %s No default broker config found for multi-session mode. "
                    "Each session must be created with a full 'broker_config' override.",
                    self.name,
                    self.log_identifier,
                )

            try:
                self._multi_session_manager = MultiSessionRequestResponseManager(
                    component=self,
                    default_session_config=default_session_config,
                    max_sessions=multi_session_config.get("max_sessions", 50),
                )
            except Exception:
                log.exception(
                    f"[{self.name}] {self.log_identifier} Failed to initialize multi-session manager",
                )
                raise ValueError("Failed to initialize multi-session manager") from None

    def create_request_response_session(
        self, session_config: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Creates a new dynamic request/response session.

        Args:
            session_config: A dictionary of configuration values for this session.
                            These values are merged with any defaults.

        Returns:
            The unique session ID of the newly created session.

        Raises:
            RuntimeError: If multi-session request/response is not enabled.
        """
        if not self._multi_session_manager:
            raise RuntimeError(
                "Multi-session request/response is not enabled for this component."
            )
        return self._multi_session_manager.create_session(session_config)

    def destroy_request_response_session(self, session_id: str) -> bool:
        """
        Destroys a dynamic request/response session and cleans up its resources.

        Args:
            session_id: The ID of the session to destroy.

        Returns:
            True if the session was found and destroyed, False otherwise.

        Raises:
            RuntimeError: If multi-session request/response is not enabled.
        """
        if not self._multi_session_manager:
            raise RuntimeError(
                "Multi-session request/response is not enabled for this component."
            )
        return self._multi_session_manager.destroy_session(session_id)

    def list_request_response_sessions(self) -> List[Dict[str, Any]]:
        """
        Returns a list of dictionaries containing detailed status for each
        active dynamic session.

        Returns:
            A list of session status dictionaries.

        Raises:
            RuntimeError: If multi-session request/response is not enabled.
        """
        if not self._multi_session_manager:
            raise RuntimeError(
                "Multi-session request/response is not enabled for this component."
            )
        return self._multi_session_manager.list_sessions()

    def is_broker_request_response_enabled(self):
        """Checks if RRC is enabled either at App level or Component level."""
        app = self.get_app()
        # Check app level first (new way)
        if app is not None and app.request_response_controller is not None:
            return True
        # Check component level (old way)
        if hasattr(self, "_component_rrc") and self._component_rrc is not None:
            return True
        return False

    def _setup_transforms(self):
        self.transforms = Transforms(
            self.config.get("input_transforms", []), log_identifier=self.log_identifier
        )

    def validate_config(self):
        """Validates the component_config against the schema in module_info."""
        config_params = self.module_info.get("config_parameters", [])
        # Only validate if schema parameters are defined
        if config_params:
            try:
                validate_config_block(
                    self.component_config, config_params, self.log_identifier
                )
            except ValueError as e:
                # Re-raise the error with more context
                raise ValueError(
                    f"Configuration error in component '{self.name}': {e}"
                ) from e
        else:
            log.debug(
                "%s No 'config_parameters' defined in module_info. Skipping config validation.",
                self.log_identifier,
            )

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
        log.debug("[%s] %s Cleaning up component", self.name, self.log_identifier)
        try:
            self.stop_component()
        except KeyboardInterrupt:
            pass
        if hasattr(self, "_component_rrc") and self._component_rrc:
            self._component_rrc = None
        if hasattr(self, "_multi_session_manager") and self._multi_session_manager:
            self._multi_session_manager.shutdown()
            self._multi_session_manager = None
        if hasattr(self, "input_queue"):
            while not self.input_queue.empty():
                try:
                    self.input_queue.get_nowait()
                except queue.Empty:
                    break

    async def do_broker_request_response_async(
        self,
        message,
        session_id: Optional[str] = None,
        stream=False,
        streaming_complete_expression=None,
        wait_for_response: bool = True,
    ):
        """
        Asynchronous wrapper for do_broker_request_response.
        Runs the blocking call in a separate thread to avoid blocking the asyncio event loop.

        Args:
            message: The request message to send.
            session_id: The ID of the dynamic session to use.
            stream: Whether the response is expected to be streaming.
            streaming_complete_expression: Expression to detect the end of a stream.
            wait_for_response: If False, sends the request and returns immediately.
        """
        return await asyncio.to_thread(
            self.do_broker_request_response,
            message,
            session_id=session_id,
            stream=stream,
            streaming_complete_expression=streaming_complete_expression,
            wait_for_response=wait_for_response,
        )

    def do_broker_request_response(
        self,
        message,
        session_id: Optional[str] = None,
        stream=False,
        streaming_complete_expression=None,
        wait_for_response: bool = True,
    ):
        """
        Performs broker request-response.
        If session_id is provided, uses the dynamic multi-session manager.
        Otherwise, falls back to the legacy App-level or Component-level controller.

        Args:
            message: The request message to send.
            session_id: The ID of the dynamic session to use.
            stream: Whether the response is expected to be streaming.
            streaming_complete_expression: Expression to detect the end of a stream.
            wait_for_response: If False, sends the request and returns immediately.
        """
        generator = None
        # New multi-session path
        if session_id:
            if not self._multi_session_manager:
                raise RuntimeError(
                    "A session_id was provided, but multi-session request/response "
                    "is not enabled for this component."
                )
            session = self._multi_session_manager.get_session(session_id)
            generator = session.do_request_response(
                message, stream, streaming_complete_expression, wait_for_response
            )
        # Legacy single-session path (backward compatibility)
        else:
            app = self.get_app()
            controller = None

            # Prioritize App-level controller (new way)
            if app and app.request_response_controller:
                controller = app.request_response_controller
                log.debug(
                    "[%s] %s Using App-level RRC.", self.name, self.log_identifier
                )
            # Fallback to Component-level controller (old way)
            elif hasattr(self, "_component_rrc") and self._component_rrc:
                controller = self._component_rrc
                log.debug(
                    "[%s] %s Using Component-level RRC.", self.name, self.log_identifier
                )

            if not controller:
                raise ValueError(
                    f"Broker request-response is not enabled for app '{app.name if app else 'unknown'}' "
                    f"or component '{self.name}'. Ensure 'request_reply_enabled: true' is set in the app's "
                    f"'broker' config (recommended) or 'enabled: true' in the component's "
                    f"'broker_request_response' config (deprecated)."
                )

            generator = controller.do_broker_request_response(
                message, stream, streaming_complete_expression, wait_for_response
            )

        # Common response handling for both paths
        if not wait_for_response:
            # For fire-and-forget, we must advance the generator once to trigger
            # the initial send_message call within the controller.
            try:
                # The generator will execute until the first yield or a return.
                # In the fire-and-forget case, it hits a 'return', which
                # raises StopIteration.
                next(generator)
            except StopIteration:
                # This is the expected outcome for a non-waiting call.
                pass
            return None  # Fire-and-forget, return immediately

        if stream:
            return generator  # Return the generator directly for streaming
        else:
            # Get the first (and only) item for non-streaming
            try:
                next_message, _ = next(generator)  # Ignore the 'last' flag
                return next_message
            except StopIteration:
                log.warning(
                    "[%s] %s RRC generator yielded no response.",
                    self.name,
                    self.log_identifier,
                )
                return None
            except TimeoutError as e:  # Catch timeout specifically
                log.exception(
                    f"[{self.name}] {self.log_identifier} RRC timed out"
                )
                raise ValueError("RRC timed out") from e  # Re-raise timeout
            except Exception as e:
                log.exception(
                    f"[{self.name}] {self.log_identifier} Error during RRC call"
                )
                raise ValueError("Error during RRC call") from e

    def handle_negative_acknowledgements(self, message, exception):
        """Handle NACK for the message."""
        log.error(
            "[%s] %s Component failed to process message. Sending Negative Acknowledgement.",
            self.name,
            self.log_identifier,
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
            log.info("[%s] Monitoring connection status stopped.", self.name)

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
                    log.debug("[%s] Automatically flushed metrics.", self.name)
        except KeyboardInterrupt:
            log.info("[%s] Monitoring stopped.", self.name)

    def get_app(self):
        """Get the app that this component belongs to"""
        return self.parent_app
