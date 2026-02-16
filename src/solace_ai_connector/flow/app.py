"""App class for the Solace AI Event Connector"""

import logging
import threading
import time
from typing import List, Dict, Any, Optional
from copy import deepcopy

from .flow import Flow

log = logging.getLogger(__name__)
from ..common.utils import (
    deep_merge,
    resolve_config_values,
)  # Import deep_merge and resolve_config_values

# Import the validation utility function
from ..common.config_validation import validate_config_block
from .request_response_flow_controller import RequestResponseFlowController

# App status constants
APP_STATUS_CREATED = "created"
APP_STATUS_STARTING = "starting"
APP_STATUS_RUNNING = "running"
APP_STATUS_STOPPING = "stopping"
APP_STATUS_STOPPED = "stopped"
APP_STATUS_ERROR = "error"


class _CombinedStopSignal:
    """Combines a connector-level and an app-level stop signal.

    Duck-typed replacement for threading.Event. Components call .is_set()
    and .wait(timeout=...) which this class supports. Returns is_set()=True
    if either the connector-level or app-level signal is set.
    """

    def __init__(self, connector_signal, app_signal):
        self._connector = connector_signal
        self._app = app_signal

    def is_set(self):
        return self._connector.is_set() or self._app.is_set()

    def set(self):
        self._app.set()

    def wait(self, timeout=None):
        # Wait on the app signal with the given timeout.
        # After waiting, return whether either signal is set.
        self._app.wait(timeout=timeout)
        return self.is_set()

    def clear(self):
        self._app.clear()


class App:
    """
    App class for the Solace AI Event Connector.
    An app is a collection of flows that are logically grouped together.
    """

    # Define the schema for app_config parameters for the base App class
    # Subclasses can override or extend this.
    app_schema: Dict[str, List[Dict[str, Any]]] = {}

    def __init__(
        self,
        app_info: Dict[str, Any],
        app_index: int,
        stop_signal,
        error_queue=None,
        instance_name=None,
        trace_queue=None,
        connector=None,
    ):
        """
        Initialize the App.

        Args:
            app_info: Info and configuration for the app (typically from YAML).
            app_index: Index of the app in the list of apps
            stop_signal: Signal to stop the app
            error_queue: Queue for error messages
            instance_name: Name of the connector instance
            trace_queue: Queue for trace messages
            connector: Reference to the parent connector
        """
        # Check if this is a custom App subclass with code-defined config
        code_config = None
        # Use 'app_config' as the standard name for code-defined config as well
        if hasattr(self.__class__, "app_config") and isinstance(
            self.__class__.app_config, dict
        ):
            log.debug("Found code-defined app_config in %s", self.__class__.__name__)
            code_config = self.__class__.app_config

        # Merge configurations: YAML (app_info) overrides code_config
        if code_config:
            # Perform a deep merge, giving precedence to app_info (YAML)
            merged_app_info = deep_merge(code_config, app_info)
            log.debug(
                "Merged app config for %s", merged_app_info.get("name", "unnamed app")
            )

            # Resolve any environment variables or other placeholders in the merged config
            resolve_config_values(merged_app_info)

        else:
            # If no code_config, app_info comes from YAML and was already resolved
            # by SolaceAiConnector.__init__
            merged_app_info = app_info

        # Store the final merged and resolved config
        self.app_info = merged_app_info
        # Extract the specific 'app_config' block AFTER merging and resolving
        self.app_config = self.app_info.get("app_config", {})
        self.app_index = app_index
        # Derive name from merged config
        self.name = self.app_info.get("name", f"app_{app_index}")
        self.num_instances = self.app_info.get("num_instances", 1)
        self.flows: List[Flow] = []
        self._connector_stop_signal = stop_signal
        self._app_stop_signal = threading.Event()
        self.stop_signal = _CombinedStopSignal(stop_signal, self._app_stop_signal)
        self.enabled = True
        self.status = APP_STATUS_CREATED
        self.error_queue = error_queue
        self.instance_name = instance_name
        self.trace_queue = trace_queue
        self.connector = connector
        self.flow_input_queues = {}
        self._broker_output_component = None  # Cache for send_message
        self.request_response_controller = None  # Initialize RRC attribute

        self._validate_app_config()

        # Initialize flows based on the final merged configuration
        self._initialize_flows()

        # Initialize RRC after flows are potentially created (though RRC doesn't depend on flows)
        broker_config = self.app_info.get("broker", {})
        if broker_config.get("request_reply_enabled", False):
            log.info(
                "Request-reply enabled for app '%s'. Initializing controller.",
                self.name,
            )
            try:
                # Instantiate RequestResponseFlowController
                # Pass the broker config section and the connector reference
                self.request_response_controller = RequestResponseFlowController(
                    config={
                        "broker_config": broker_config
                    },  # Pass broker config under 'broker_config' key
                    connector=self.connector,
                )
                # Store controller instance (already done by assignment above)
            except Exception:
                log.exception(
                    f"Failed to initialize RequestResponseFlowController for app '{self.name}'."
                )
                # Decide if this should be a fatal error for the app
                raise

    def _validate_app_config(self):
        """Validates self.app_config against the class's app_schema."""
        # Use getattr to safely access the class attribute
        schema = getattr(self.__class__, "app_schema", None)
        if schema and isinstance(schema, dict):
            schema_params = schema.get("config_parameters", [])
            # Ensure schema_params is a list before proceeding
            if schema_params and isinstance(schema_params, list):
                log.debug(
                    "Validating app_config for app '%s' against schema.", self.name
                )
                try:
                    # Validate self.app_config which holds the merged app-level config block
                    validate_config_block(
                        self.app_config, schema_params, f"App '{self.name}'"
                    )
                except ValueError as e:
                    # Re-raise with context
                    raise ValueError(
                        f"Configuration error in app '{self.name}': {e}"
                    ) from e
            else:
                # Log if 'config_parameters' exists but is not a valid list
                if "config_parameters" in schema:
                    log.warning(
                        "Invalid 'config_parameters' in app_schema for app '%s' (must be a list). Skipping validation.",
                        self.name,
                    )
                else:
                    log.debug(
                        "No 'config_parameters' found in app_schema for app '%s'. Skipping validation.",
                        self.name,
                    )
        else:
            # Log if 'app_schema' is missing or not a dict
            log.debug(
                "No valid app_schema defined for app class '%s'. Skipping validation.",
                self.__class__.__name__,
            )

    def _initialize_flows(self):
        """Create flows based on the final app configuration."""
        try:
            # Determine mode based on the presence of the 'flows' key
            is_standard = "flows" in self.app_info

            if is_standard:
                # --- Standard App Mode ---
                log.debug("Initializing standard flows for app %s", self.name)
                # Process flows even if the list is empty (valid standard app structure)
                for index, flow_config in enumerate(self.app_info.get("flows", [])):
                    log.debug(
                        "Creating flow %s in app %s", flow_config.get("name"), self.name
                    )
                    num_instances = flow_config.get("num_instances", 1)
                    if num_instances < 1:
                        num_instances = 1
                    for i in range(num_instances):
                        flow_instance = self.create_flow(flow_config, index, i)
                        flow_input_queue = flow_instance.get_flow_input_queue()
                         # Use flow name without index for single instance flows
                        flow_name = flow_config.get('name')
                        if num_instances == 1:
                            # For single instance flows, don't add an index
                            self.flow_input_queues[flow_name] = flow_input_queue
                        else:
                            # For multiple instances, add an index
                            queue_key = f"{flow_name}_{i}"
                            self.flow_input_queues[queue_key] = flow_input_queue
                        self.flows.append(flow_instance)
            else:
                # --- Simplified App Mode ---
                log.debug("Initializing simplified flow for app %s", self.name)
                # Validate presence of broker and components if not a custom App subclass
                # (Custom subclasses might define flows differently)
                if isinstance(self, App):  # Only validate for the base App class
                    if (
                        "broker" not in self.app_info
                        or "components" not in self.app_info
                    ):
                        raise ValueError(
                            f"Simplified app '{self.name}' must define 'broker' and 'components' keys "
                            "(or be a standard app with a 'flows' key)."
                        )
                # Call helper to generate implicit flow config
                flow_config = self._create_simplified_flow_config()
                # Create the single implicit flow
                flow_instance = self.create_flow(flow_config, 0, 0)
                flow_input_queue = flow_instance.get_flow_input_queue()
                self.flow_input_queues[flow_config.get("name")] = flow_input_queue
                self.flows.append(flow_instance)

        except Exception:
            log.exception(f"Error initializing flows for app {self.name}")
            raise ValueError(
                f"Error initializing flows for app '{self.name}'. Check the configuration."
            )

    def _create_simplified_flow_config(self) -> Dict[str, Any]:
        """Creates the implicit flow configuration for a simplified app."""
        broker_config = self.app_info.get("broker", {})
        user_components = self.app_info.get("components", [])
        flow_components = []

        # Add BrokerInput if enabled
        if broker_config.get("input_enabled", False):
            # Collect all subscriptions from user components
            all_subscriptions = [
                sub for comp in user_components for sub in comp.get("subscriptions", [])
            ]
            if not all_subscriptions:
                log.warning(
                    "Simplified app '%s' has input_enabled=true but no subscriptions defined in components.",
                    self.name,
                )

            input_comp_config = {
                "component_name": f"{self.name}_broker_input",
                "component_module": "broker_input",
                # Pass relevant broker config keys to BrokerInput's component_config
                "component_config": {
                    "broker_type": broker_config.get("broker_type"),
                    "dev_mode": broker_config.get("dev_mode"),
                    "broker_url": broker_config.get("broker_url"),
                    "broker_username": broker_config.get("broker_username"),
                    "broker_password": broker_config.get("broker_password"),
                    "broker_vpn": broker_config.get("broker_vpn"),
                    "reconnection_strategy": broker_config.get("reconnection_strategy"),
                    "retry_interval": broker_config.get("retry_interval"),
                    "retry_count": broker_config.get("retry_count"),
                    "trust_store_path": broker_config.get("trust_store_path"),
                    "broker_queue_name": broker_config.get(
                        "queue_name"
                    ),  # Use the main queue name
                    "temporary_queue": broker_config.get("temporary_queue", False),
                    "create_queue_on_start": broker_config.get(
                        "create_queue_on_start", True
                    ),
                    "payload_encoding": broker_config.get("payload_encoding", "utf-8"),
                    "payload_format": broker_config.get("payload_format", "json"),
                    "max_redelivery_count": broker_config.get("max_redelivery_count"),
                    "broker_subscriptions": all_subscriptions,  # Pass collected subscriptions
                },
            }
            flow_components.append(input_comp_config)

        # Add SubscriptionRouter if needed (input enabled and more than one user component)
        if broker_config.get("input_enabled", False) and len(user_components) > 1:
            router_comp_config = {
                "component_name": f"{self.name}_router",
                "component_module": "subscription_router",  # Assuming this module exists
                # Router needs access to the app's component list for routing rules
                "component_config": {
                    # Pass the original user components list as defined in the app config
                    "app_components_config_ref": self.app_info.get("components", [])
                },
            }
            flow_components.append(router_comp_config)

        # Add User Components (make a deep copy to avoid modification issues)
        flow_components.extend(deepcopy(user_components))

        # Add BrokerOutput if enabled
        if broker_config.get("output_enabled", False):
            output_comp_config = {
                "component_name": f"{self.name}_broker_output",
                "component_module": "broker_output",
                # Pass relevant broker config keys to BrokerOutput's component_config
                "component_config": {
                    "broker_type": broker_config.get("broker_type"),
                    "dev_mode": broker_config.get("dev_mode"),
                    "broker_url": broker_config.get("broker_url"),
                    "broker_username": broker_config.get("broker_username"),
                    "broker_password": broker_config.get("broker_password"),
                    "broker_vpn": broker_config.get("broker_vpn"),
                    "reconnection_strategy": broker_config.get("reconnection_strategy"),
                    "retry_interval": broker_config.get("retry_interval"),
                    "retry_count": broker_config.get("retry_count"),
                    "trust_store_path": broker_config.get("trust_store_path"),
                    "payload_encoding": broker_config.get("payload_encoding", "utf-8"),
                    "payload_format": broker_config.get("payload_format", "json"),
                    "propagate_acknowledgements": broker_config.get(
                        "propagate_acknowledgements", True
                    ),
                    # Add other relevant output-specific configs if needed
                },
            }
            flow_components.append(output_comp_config)

        # Construct the final flow dictionary
        return {"name": f"{self.name}_implicit_flow", "components": flow_components}

    def create_flow(self, flow: dict, index: int, flow_instance_index: int) -> Flow:
        """
        Create a single flow.

        Args:
            flow: Flow configuration
            index: Index of the flow in the list of flows
            flow_instance_index: Index of the flow instance

        Returns:
            Flow: The created flow
        """
        return Flow(
            flow_config=flow,
            flow_index=index,
            flow_instance_index=flow_instance_index,
            stop_signal=self.stop_signal,
            error_queue=self.error_queue,
            instance_name=self.instance_name,
            trace_queue=self.trace_queue,
            connector=self.connector,
            app=self,
        )

    def run(self):
        """Run all flows in the app"""
        self.status = APP_STATUS_STARTING
        for flow in self.flows:
            flow.run()
        self.status = APP_STATUS_RUNNING

    def wait_for_flows(self):
        """Wait for all flows to complete"""
        for flow in self.flows:
            flow.wait_for_threads()

    def is_startup_complete(self) -> bool:
        """
        Check if the app has completed its startup/initialization phase.

        Override this method in custom app classes to provide app-specific startup logic.
        The default implementation always returns True, indicating startup is complete
        once the app is created.

        Unlike is_ready(), this method is only checked until it returns True, then the
        startup state is latched. Use this for one-time initialization checks.

        Examples of custom startup checks:
        - ML model loaded into memory
        - Database connection pool initialized
        - Cache warmed up
        - Initial data sync completed
        - Message broker subscriptions active

        Returns:
            bool: True if startup is complete, False if still initializing
        """
        return True

    def is_ready(self) -> bool:
        """
        Check if the app is ready to process messages.

        Override this method in custom app classes to provide app-specific readiness logic.
        The default implementation always returns True, relying on thread health checks.

        Unlike is_startup_complete(), this method is called continuously and can toggle
        between ready and not ready based on current operational state.

        Examples of custom readiness checks:
        - Database connection established
        - External service available
        - Configuration loaded and validated
        - Cache warmed up

        Returns:
            bool: True if the app is ready, False otherwise
        """
        return True

    def pre_stop(self, timeout=30):
        """Override in subclasses to do graceful shutdown before component threads stop.

        Use this to:
        - Stop accepting new work (e.g., unsubscribe from request topics)
        - Wait for in-flight work to complete
        - Clean up app-specific state (sessions, task contexts)

        The stop signal has NOT been set yet when this is called, so components
        are still running and can finish processing in-flight messages.

        Args:
            timeout: Time budget in seconds. Return before this expires.
        """

    def stop(self, timeout=30):
        """Stop the app gracefully.

        Three-phase shutdown:
        1. pre_stop() — app-specific drain (components still running)
        2. Set stop signal — component run loops exit
        3. Cleanup — disconnect broker, drain queues

        Args:
            timeout: Maximum time in seconds for the entire stop operation.
        """
        if self.status == APP_STATUS_STOPPED:
            return
        log.info("Stopping app '%s' (timeout=%ds)", self.name, timeout)
        self.status = APP_STATUS_STOPPING

        # Phase 1: App-specific graceful drain
        start = time.monotonic()
        try:
            self.pre_stop(timeout=timeout)
        except Exception:
            log.exception("Error in pre_stop for app '%s'", self.name)
        elapsed = time.monotonic() - start
        remaining = max(0, timeout - elapsed)

        # Phase 2: Stop component threads
        self._app_stop_signal.set()
        all_threads = [
            thread for flow in self.flows for thread in flow.threads
        ]
        if all_threads and remaining > 0:
            per_thread_timeout = remaining / len(all_threads)
            for thread in all_threads:
                if thread.is_alive():
                    thread.join(timeout=per_thread_timeout)
            still_alive = [t for t in all_threads if t.is_alive()]
            if still_alive:
                log.warning(
                    "App '%s': %d threads still alive after timeout",
                    self.name,
                    len(still_alive),
                )

        # Phase 3: Cleanup
        for flow in self.flows:
            try:
                flow.cleanup()
            except Exception:
                log.exception("Error cleaning up flow in app '%s'", self.name)
        self.flows.clear()
        self.flow_input_queues.clear()
        self._broker_output_component = None
        if self.request_response_controller:
            self.request_response_controller = None
        self.status = APP_STATUS_STOPPED
        self.enabled = False
        log.info("App '%s' stopped", self.name)

    def start(self):
        """Start (or restart) the app.

        Only callable when the app is in 'stopped' status. Recreates flows,
        components, and threads from the current configuration.

        Raises:
            RuntimeError: If the app is not in 'stopped' status.
        """
        if self.status != APP_STATUS_STOPPED:
            raise RuntimeError(
                f"Cannot start app '{self.name}': status is '{self.status}', expected '{APP_STATUS_STOPPED}'"
            )
        log.info("Starting app '%s'", self.name)

        # Reset the app-level stop signal
        self._app_stop_signal = threading.Event()
        self.stop_signal = _CombinedStopSignal(
            self._connector_stop_signal, self._app_stop_signal
        )

        # Reinitialize flows (creates components and threads)
        self._initialize_flows()

        # Reinitialize RRC if needed
        broker_config = self.app_info.get("broker", {})
        if broker_config.get("request_reply_enabled", False):
            try:
                self.request_response_controller = RequestResponseFlowController(
                    config={"broker_config": broker_config},
                    connector=self.connector,
                )
            except Exception:
                log.exception(
                    "Failed to initialize RRC for app '%s' during start",
                    self.name,
                )
                self.status = APP_STATUS_ERROR
                raise

        # Run all flows
        self.run()

        # Re-register flows with connector
        if self.connector and hasattr(self.connector, "_register_app_flows"):
            self.connector._register_app_flows(self)

        self.enabled = True

    def get_info(self):
        """Return a dict with basic information about the app.

        Returns:
            Dict with name, enabled, status, num_instances, and app_module.
        """
        return {
            "name": self.name,
            "enabled": self.enabled,
            "status": self.status,
            "num_instances": self.num_instances,
            "app_module": self.app_info.get("app_module"),
        }

    def get_management_endpoints(self):
        """Return a list of custom management endpoints for this app.

        Override in subclasses to advertise type-specific management endpoints.

        Returns:
            List of endpoint descriptors (dicts with method, path, description).
        """
        return []

    def handle_management_request(self, method, path_parts, body, context):
        """Handle a custom management request.

        Override in subclasses to handle type-specific management requests.

        Args:
            method: HTTP method (GET, POST, PUT, PATCH, DELETE)
            path_parts: List of path segments after /apps/{name}/
            body: Request body (dict)
            context: Request context (dict with user identity, etc.)

        Returns:
            Result dict on success, or None if the endpoint is not handled.
        """
        return None

    def cleanup(self):
        """Clean up resources and ensure all threads are properly joined"""
        log.info("Cleaning up app: %s", self.name)
        # Clean up the request response controller if it exists
        if self.request_response_controller:
            try:
                # Assuming RRC has a cleanup method or similar
                # If not, cleanup might involve stopping its internal flow/app
                # For now, we rely on the connector cleaning up all apps/flows
                pass  # RRC's internal app/flow will be cleaned by connector.cleanup()
            except Exception:
                log.exception(
                    f"Error cleaning up RequestResponseFlowController in app {self.name}"
                )
            self.request_response_controller = None

        for flow in self.flows:
            try:
                flow.cleanup()
            except Exception:
                log.exception(f"Error cleaning up flow in app {self.name}")
        self.flows.clear()
        self.flow_input_queues.clear()
        self._broker_output_component = None  # Clear cache

    def get_config(self, key=None, default=None):
        """
        Get a configuration value from the app's 'app_config' block.

        Args:
            key: Configuration key
            default: Default value if key is not found

        Returns:
            The configuration value or default
        """
        # self.app_config holds the 'app_config:' block from the merged app_info
        return self.app_config.get(key, default)

    def send_message(
        self, payload: Any, topic: str, user_properties: Optional[Dict] = None
    ):
        """
        Sends a message via the implicit BrokerOutput component of a simplified app.

        Args:
            payload: The message payload.
            topic: The destination topic.
            user_properties: Optional dictionary of user properties.
        """
        # Import locally to avoid circular dependency issues at module level
        from ..common.message import Message
        from ..common.event import Event, EventType

        # Check if output is enabled for this app
        if not self.app_info.get("broker", {}).get("output_enabled", False):
            log.warning(
                "App '%s' attempted to send a message, but 'output_enabled' is false. Message discarded.",
                self.name,
            )
            return

        # Find the BrokerOutput component instance (cache it after first find)
        if self._broker_output_component is None:
            broker_output_instance = None
            # Simplified apps have only one flow
            if self.flows:
                flow = self.flows[0]
                # BrokerOutput is typically the last component in the implicit flow
                if flow.component_groups:
                    # Find the BrokerOutput component by class name
                    for group in reversed(flow.component_groups):  # Search from end
                        if group:
                            comp = group[0]  # Check first instance in group
                            if comp.module_info.get("class_name") == "BrokerOutput":
                                broker_output_instance = comp
                                break
                            # Fallback check on module name (less reliable)
                            elif comp.config.get("component_module") == "broker_output":
                                broker_output_instance = comp
                                break

            if broker_output_instance:
                self._broker_output_component = broker_output_instance
            else:
                log.error(
                    "App '%s' could not find the implicit BrokerOutput component to send a message.",
                    self.name,
                )
                return

        # Create the output data structure expected by BrokerOutput
        output_data = {
            "payload": payload,
            "topic": topic,
            "user_properties": user_properties or {},
        }

        # Create a Message object and place the output data in 'previous'
        # This mimics how data flows from a preceding component to BrokerOutput
        msg = Message()
        msg.set_previous(output_data)

        # Create an Event to enqueue
        event = Event(EventType.MESSAGE, msg)

        # Enqueue the event to the BrokerOutput component
        try:
            log.debug(
                "App '%s' sending message via implicit BrokerOutput to topic '%s'",
                self.name,
                topic,
            )
            self._broker_output_component.enqueue(event)
        except Exception:
            log.exception(
                f"App '{self.name}' failed to enqueue message to BrokerOutput."
            )

    @classmethod
    def create_from_flows(
        cls, flows: List[Dict[str, Any]], app_name: str, **kwargs
    ) -> "App":
        """
        Create an app from a list of flows (for backward compatibility).

        Args:
            flows: List of flow configurations
            app_name: Name for the app
            **kwargs: Additional arguments for App constructor

        Returns:
            App: The created app
        """
        app_info = {"name": app_name, "flows": flows, "app_config": {}}
        # Note: This path won't automatically merge with code_config unless
        # a specific subclass is used that defines it.
        # It also won't resolve static config within the 'flows' structure here.
        return cls(app_info=app_info, **kwargs)
