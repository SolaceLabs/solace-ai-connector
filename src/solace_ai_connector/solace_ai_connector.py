"""Entry point for the Solace AI Event Connector"""

import threading
import queue
import traceback
import os
import time

from datetime import datetime
from typing import List, Dict, Any
from .common.log import log, setup_log
from .common.utils import resolve_config_values, import_module
from .flow.flow import Flow
from .flow.app import App
from .flow.timer_manager import TimerManager
from .common.event import Event, EventType
from .services.cache_service import CacheService, create_storage_backend
from .common.monitoring import Monitoring


class SolaceAiConnector:
    """Solace AI Connector"""

    def __init__(
        self, config, event_handlers=None, error_queue=None, config_filenames=None
    ):
        self.config = config or {}
        self.apps: List[App] = []
        self.flows: List[Flow] = []  # For backward compatibility
        self.trace_queue = None
        self.trace_thread = None
        self.flow_input_queues = {}
        self.stop_signal = threading.Event()
        self.event_handlers = event_handlers or {}
        self.error_queue = error_queue if error_queue else queue.Queue()
        self.config_filenames = config_filenames or []
        self.setup_logging()
        self.setup_trace()
        resolve_config_values(self.config)
        self.validate_config()
        self.instance_name = self.config.get("instance_name", "solace_ai_connector")
        self.timer_manager = TimerManager(self.stop_signal)
        self.cache_service = self.setup_cache_service()

        # Initialize monitoring
        monitoring_config = self.config.get("monitoring", None)
        self.monitoring = Monitoring(monitoring_config)

    def run(self):
        """Run the Solace AI Event Connector"""
        log.info("Starting Solace AI Event Connector")
        try:
            self.create_apps()

            # Call the on_flow_creation event handler
            on_flow_creation = self.event_handlers.get("on_flow_creation")
            if on_flow_creation:
                on_flow_creation(self.flows)

            log.info("Solace AI Event Connector started successfully")
        except KeyboardInterrupt:
            log.info("Received keyboard interrupt - stopping")

            raise KeyboardInterrupt from None
        except Exception:
            log.error("Error during Solace AI Event Connector startup")
            raise ValueError("An error occurred during startup") from None

    def create_apps(self):
        """Create apps from the configuration"""
        try:
            # Check if there are apps defined in the configuration
            apps_config = self.config.get("apps", [])

            # If there are no apps defined but there are flows, create a default app
            # This should be rare now that we handle this in main.py, but keeping for robustness
            if not apps_config and self.config.get("flows"):
                # Use the first config filename as the app name if available
                app_name = "default_app"
                if self.config_filenames:
                    # Extract filename without extension
                    app_name = os.path.splitext(
                        os.path.basename(self.config_filenames[0])
                    )[0]

                log.info("Creating default app '%s' from flows configuration", app_name)
                # Create app info structure for the default app
                default_app_info = {
                    "name": app_name,
                    "flows": self.config.get("flows", []),
                    # Add default app_config if needed, or leave empty
                    "app_config": {},
                }
                app = App(
                    app_info=default_app_info,
                    app_index=0,
                    stop_signal=self.stop_signal,
                    error_queue=self.error_queue,
                    instance_name=self.instance_name,
                    trace_queue=self.trace_queue,
                    connector=self,
                )
                self.apps.append(app)

                # For backward compatibility, also add flows to the flows list
                self.flows.extend(app.flows)

                # Add flow input queues to the connector's flow_input_queues
                for name, queue in app.flow_input_queues.items():
                    self.flow_input_queues[name] = queue
            else:
                # Create apps from the apps configuration
                for index, app_info in enumerate(apps_config):
                    log.info("Creating app %s", app_info.get("name"))
                    num_instances = app_info.get("num_instances", 1)
                    if num_instances < 1:
                        num_instances = 1
                        log.warning(
                            "Number of instances for app %s is less than 1. Setting it to 1",
                            app_info.get("name"),
                        )

                    for i in range(num_instances):

                        # Does this have a custom App module
                        app_module = app_info.get("app_module", None)
                        app_base_path = app_info.get("app_base_path", None)
                        app_package = app_info.get("app_package", None)
                        if app_module:
                            imported_module = import_module(
                                app_module, app_base_path, app_package
                            )
                            # Attempt to get info, but allow it to be missing for custom apps
                            info = getattr(imported_module, "info", None)
                            class_name = None
                            if info:
                                class_name = info.get("class_name")

                            if class_name:
                                app_class = getattr(imported_module, class_name)
                            else:
                                # If no class_name in info, assume the module itself might contain the App subclass
                                # Look for a class inheriting from App in the module
                                found_class = None
                                for name, obj in imported_module.__dict__.items():
                                    if (
                                        isinstance(obj, type)
                                        and issubclass(obj, App)
                                        and obj is not App
                                    ):
                                        if found_class:
                                            raise ValueError(
                                                f"App module '{app_module}' contains multiple App subclasses. Specify class_name in info."
                                            ) from None
                                        found_class = obj
                                if not found_class:
                                    raise ValueError(
                                        f"App module '{app_module}' does not contain an App subclass or define class_name in info."
                                    ) from None
                                app_class = found_class
                                log.debug(
                                    "Using App subclass %s found in module %s",
                                    app_class.__name__,
                                    app_module,
                                )

                        else:
                            # Use the default App class
                            app_class = App

                        app_obj = app_class(
                            app_info=app_info,
                            app_index=index,
                            stop_signal=self.stop_signal,
                            error_queue=self.error_queue,
                            instance_name=self.instance_name,
                            trace_queue=self.trace_queue,
                            connector=self,
                        )
                        self.apps.append(app_obj)

                        # For backward compatibility, also add flows to the flows list
                        self.flows.extend(app_obj.flows)
                        # Add flow input queues to the connector's flow_input_queues
                        for name, queue in app_obj.flow_input_queues.items():
                            self.flow_input_queues[name] = queue

            # Run all apps
            for app_obj in self.apps:
                app_obj.run()

        except KeyboardInterrupt:
            log.info("Received keyboard interrupt - stopping")
            raise KeyboardInterrupt from None
        except Exception:
            log.error("Error creating apps")
            raise ValueError("An error occurred during app creation") from None

    def create_internal_app(self, app_name: str, flows: List[Dict[str, Any]]) -> App:
        """
        Create an internal app for use by components like the request-response controller.

        Args:
            app_name: Name for the app
            flows: List of flow configurations

        Returns:
            App: The created app
        """
        app_info = {"name": app_name, "flows": flows, "app_config": {}}

        # Create the app
        app = App(
            app_info=app_info,
            app_index=len(self.apps),
            stop_signal=self.stop_signal,
            error_queue=self.error_queue,
            instance_name=self.instance_name,
            trace_queue=self.trace_queue,
            connector=self,
        )

        # Add the app to the connector's apps list
        self.apps.append(app)

        # Add flow input queues to the connector's flow_input_queues
        for name, queue in app.flow_input_queues.items():
            self.flow_input_queues[name] = queue

        return app

    def create_flows(self):
        """
        Legacy method for backward compatibility.
        This is now handled by create_apps().
        """
        self.create_apps()

    def create_flow(self, flow: dict, index: int, flow_instance_index: int):
        """
        Legacy method for backward compatibility.
        This is now handled by App.create_flow().
        """
        # This should not be called directly anymore
        raise NotImplementedError(
            "create_flow is deprecated, use create_apps instead"
        ) from None

    def send_message_to_flow(self, flow_name, message):
        """Send a message to a flow"""
        flow_input_queue = self.flow_input_queues.get(flow_name)
        if flow_input_queue:
            event = Event(EventType.MESSAGE, message)
            flow_input_queue.put(event)
        else:
            log.error("Can't send message to flow %s. Not found", flow_name)

    def wait_for_flows(self):
        """Wait for the flows to finish"""
        while not self.stop_signal.is_set():
            try:
                all_threads = [
                    thread
                    for app in self.apps
                    for flow in app.flows
                    for thread in flow.threads
                ]
                if not all_threads:
                    break  # No threads to wait for
                # Wait for any thread to finish or timeout
                # This prevents blocking indefinitely if one thread hangs
                for thread in all_threads:
                    thread.join(timeout=0.1)
                # Check if all threads are done
                if not any(thread.is_alive() for thread in all_threads):
                    break
            except KeyboardInterrupt:
                log.info("Received keyboard interrupt - stopping")
                raise KeyboardInterrupt from None

    def cleanup(self):
        """Clean up resources and ensure all threads are properly joined"""
        log.info("Cleaning up Solace AI Event Connector")
        for app in self.apps:
            try:
                app.cleanup()
            except Exception:
                log.error("Error cleaning up app")
        self.apps.clear()
        self.flows.clear()  # Keep for backward compatibility refs?

        # Clean up queues
        for queue_name, q in self.flow_input_queues.items():
            try:
                while not queue.empty():
                    queue.get_nowait()
            except Exception:
                log.error(f"Error cleaning queue {queue_name}")
        self.flow_input_queues.clear()

        if hasattr(self, "trace_queue") and self.trace_queue:
            self.trace_queue.put(None)  # Signal the trace thread to stop
        if self.trace_thread and self.trace_thread.is_alive():
            self.trace_thread.join(timeout=1.0)
        if hasattr(self, "cache_check_thread") and self.cache_check_thread.is_alive():
            self.cache_check_thread.join(
                timeout=1.0
            )  # Should be stopped by cache_service.stop()
        if hasattr(self, "error_queue"):
            # Don't put None here, error queue might be shared or externally managed
            pass

        self.timer_manager.cleanup()
        log.info("Cleanup completed")

    def setup_logging(self):
        """Setup logging"""

        log_config = self.config.get("log", {})
        stdout_log_level = log_config.get("stdout_log_level", "INFO")
        log_file_level = log_config.get("log_file_level", "INFO")
        log_file = log_config.get("log_file", "solace_ai_connector.log")
        log_format = log_config.get("log_format", "pipe-delimited")

        # Get logback values
        logback = log_config.get("logback", {})

        setup_log(
            log_file,
            stdout_log_level,
            log_file_level,
            log_format,
            logback,
        )

    def setup_trace(self):
        """Setup trace"""
        trace_config = self.config.get("trace", {})
        trace_file = trace_config.get("trace_file", None)
        if trace_file:
            log.info("Setting up trace to file %s", trace_file)
            # Create a trace queue
            self.trace_queue = queue.Queue()
            # Start a new thread to handle trace messages
            self.trace_thread = threading.Thread(
                target=self.handle_trace, args=(trace_file,), daemon=True
            )
            self.trace_thread.start()

    def handle_trace(self, trace_file):
        """Handle trace messages - this is a separate thead"""

        # Create the trace file directory if it doesn't exist
        trace_dir = os.path.dirname(trace_file)
        if trace_dir and not os.path.exists(trace_dir):
            os.makedirs(trace_dir)

        try:
            with open(trace_file, "a", encoding="utf-8") as f:
                while True:
                    # Get the next trace message
                    try:
                        trace_message = self.trace_queue.get(timeout=1)
                        if trace_message is None:  # Check for stop signal
                            break
                        # Write the trace message to the file with a timestamp
                        timestamp = datetime.now().isoformat()
                        f.write(f"{timestamp}: {trace_message}\n")
                        f.flush()

                    except queue.Empty:
                        if self.stop_signal.is_set():
                            break
                        continue
        except Exception:
            log.error("Error in trace handler thread")

    def validate_config(self):
        """Validate the configuration structure."""
        if not self.config:
            raise ValueError("No config provided") from None

        # Check if either apps or flows are defined at the top level
        if not self.config.get("apps") and not self.config.get("flows"):
            raise ValueError("No apps or flows defined in configuration file") from None

        if not self.config.get("log"):
            log.warning("No log config provided - using defaults")

        # Validate apps if defined
        if self.config.get("apps"):
            if not isinstance(self.config.get("apps"), list):
                raise ValueError("'apps' must be a list") from None

            for index, app in enumerate(self.config.get("apps", [])):
                if not isinstance(app, dict):
                    raise ValueError(
                        f"App definition at index {index} must be a dictionary"
                    ) from None

                if not app.get("name"):
                    raise ValueError(
                        f"App name not provided in app definition at index {index}"
                    ) from None
                app_name = app.get("name")

                # --- Modified Validation Logic ---
                # If app_module is defined, skip the structural check here.
                # The App constructor will handle validation after merging.
                if app.get("app_module"):
                    log.debug(
                        "Skipping structural validation for app '%s' (using app_module)",
                        app_name,
                    )
                    # Basic validation for app_module itself could be added here if needed
                else:
                    # Perform structural validation only for YAML-defined apps without app_module
                    has_flows = "flows" in app
                    has_broker = "broker" in app
                    has_components = "components" in app

                    if not has_flows and not (has_broker and has_components):
                        raise ValueError(
                            f"App '{app_name}' must define either 'flows' or both 'broker' and 'components'"
                        ) from None
                    if has_flows and (has_broker or has_components):
                        log.warning(
                            "App '%s' defines both 'flows' and 'broker'/'components'. "
                            "The 'broker' and 'components' keys will be ignored (standard mode).",
                            app_name,
                        )

                    # Simplified Mode Validation (only if structure implies simplified)
                    if has_broker and has_components and not has_flows:
                        log.debug("Validating simplified app '%s'", app_name)
                        broker_config = app.get("broker")
                        components_config = app.get("components")

                        # Validate broker structure
                        if not isinstance(broker_config, dict):
                            raise ValueError(
                                f"App '{app_name}' has invalid 'broker' section (must be a dictionary)"
                            ) from None
                        required_broker_keys = [
                            "broker_url",
                            "broker_username",
                            "broker_password",
                            "broker_vpn",
                        ]
                        for key in required_broker_keys:
                            if not broker_config.get(key):
                                raise ValueError(
                                    f"App '{app_name}' broker config missing required key: '{key}'"
                                ) from None
                        if broker_config.get("input_enabled") and not broker_config.get(
                            "queue_name"
                        ):
                            raise ValueError(
                                f"App '{app_name}' broker config missing 'queue_name' when 'input_enabled' is true"
                            ) from None

                        # Validate components is a list
                        if not isinstance(components_config, list):
                            raise ValueError(
                                f"App '{app_name}' has invalid 'components' section (must be a list)"
                            ) from None
                        if not components_config:
                            raise ValueError(
                                f"App '{app_name}' must have at least one component defined in 'components'"
                            ) from None

                        # Validate each component entry
                        for comp_index, component in enumerate(components_config):
                            if not isinstance(component, dict):
                                raise ValueError(
                                    f"App '{app_name}' component definition at index {comp_index} must be a dictionary"
                                ) from None
                            if not component.get("name"):
                                raise ValueError(
                                    f"App '{app_name}' component at index {comp_index} missing 'name'"
                                ) from None
                            comp_name = component.get("name")
                            if not component.get(
                                "component_module"
                            ) and not component.get("component_class"):
                                raise ValueError(
                                    f"App '{app_name}' component '{comp_name}' missing 'component_module' or 'component_class'"
                                ) from None

                            # Validate subscriptions if input is enabled
                            if broker_config.get("input_enabled"):
                                subscriptions = component.get("subscriptions")
                                if not subscriptions:
                                    log.warning(
                                        "App '%s' component '%s' has no 'subscriptions' defined, but input is enabled.",
                                        app_name,
                                        comp_name,
                                    )
                                elif not isinstance(subscriptions, list):
                                    raise ValueError(
                                        f"App '{app_name}' component '{comp_name}' has invalid 'subscriptions' (must be a list)"
                                    ) from None
                                else:
                                    for sub_index, sub in enumerate(subscriptions):
                                        if not isinstance(sub, dict):
                                            raise ValueError(
                                                f"App '{app_name}' component '{comp_name}' subscription at index {sub_index} must be a dictionary"
                                            ) from None
                                        if not sub.get("topic"):
                                            raise ValueError(
                                                f"App '{app_name}' component '{comp_name}' subscription at index {sub_index} missing 'topic'"
                                            ) from None

                    # Standard Mode Validation (only if structure implies standard)
                    elif has_flows:
                        log.debug("Validating standard app '%s'", app_name)
                        self._validate_flows(app.get("flows"), f"app '{app_name}'")
                # --- End Modified Validation Logic ---

        # Validate top-level flows (for backward compatibility)
        if self.config.get("flows"):
            if not isinstance(self.config.get("flows"), list):
                raise ValueError("'flows' at the top level must be a list") from None
            if not self.config.get(
                "apps"
            ):  # Only validate top-level if no apps are defined
                log.warning(
                    "Using deprecated top-level 'flows' definition. Consider defining flows within an 'apps' structure."
                )
                self._validate_flows(self.config.get("flows"), "top level")
            else:
                log.warning(
                    "Ignoring top-level 'flows' definition because 'apps' is also defined."
                )

    def _validate_flows(self, flows, context):
        """Validate flows configuration (helper method)."""
        if not isinstance(flows, list):
            raise ValueError(f"Flows definition in {context} must be a list") from None

        for index, flow in enumerate(flows):
            if not isinstance(flow, dict):
                raise ValueError(
                    f"Flow definition at index {index} in {context} must be a dictionary"
                ) from None
            if not flow.get("name"):
                raise ValueError(
                    f"Flow name not provided in flow {index} of {context}"
                ) from None
            flow_name = flow.get("name")

            if "components" not in flow:  # Check presence of the key
                raise ValueError(
                    f"Flow components list not provided in flow '{flow_name}' of {context}"
                ) from None

            # Verify that the components list is a list
            if not isinstance(flow.get("components"), list):
                raise ValueError(
                    f"Flow components is not a list in flow '{flow_name}' of {context}"
                ) from None
            if not flow.get("components"):  # Check if list is empty
                raise ValueError(
                    f"Flow '{flow_name}' in {context} must have at least one component"
                ) from None

            # Loop through the components and validate them
            for component_index, component in enumerate(flow.get("components", [])):
                if not isinstance(component, dict):
                    raise ValueError(
                        f"Component definition at index {component_index} in flow '{flow_name}' of {context} must be a dictionary"
                    ) from None
                if not component.get("component_name"):
                    raise ValueError(
                        f"component_name not provided in flow '{flow_name}', component {component_index} of {context}"
                    ) from None
                comp_name = component.get("component_name")

                # In standard flows, component_module or component_class is required
                if not component.get("component_module") and not component.get(
                    "component_class"
                ):
                    raise ValueError(
                        f"Either 'component_module' or 'component_class' must be provided for component '{comp_name}' in flow '{flow_name}' of {context}"
                    ) from None

    def get_flows(self):
        """Return the flows"""
        return self.flows

    def get_flow(self, flow_name):
        """Return a specific flow by name"""
        for flow in self.flows:
            if flow.name == flow_name:
                return flow
        return None

    def get_apps(self):
        """Return the apps"""
        return self.apps

    def get_app(self, app_name):
        """Return a specific app by name"""
        for app in self.apps:
            if app.name == app_name:
                return app
        return None

    def setup_cache_service(self):
        """Setup the cache service"""
        cache_config = self.config.get("cache", {})
        backend_type = cache_config.get("backend", "memory")
        # Pass kwargs to allow backend-specific config like connection_string
        backend = create_storage_backend(backend_type, **cache_config)
        return CacheService(backend)

    def stop(self):
        """Stop the Solace AI Event Connector"""
        log.info("Stopping Solace AI Event Connector")
        self.stop_signal.set()

        # Stop core services first
        self.timer_manager.stop()  # Stop the timer manager first
        self.cache_service.stop()  # Stop the cache service

        # Wait briefly for threads to acknowledge stop signal
        time.sleep(0.2)

        # Join threads if needed (moved from wait_for_flows)
        all_threads = [
            thread for app in self.apps for flow in app.flows for thread in flow.threads
        ]
        for thread in all_threads:
            if thread.is_alive():
                thread.join(timeout=1.0)  # Give threads a chance to exit cleanly

        if self.trace_thread and self.trace_thread.is_alive():
            self.trace_thread.join(timeout=1.0)
