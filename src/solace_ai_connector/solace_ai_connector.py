"""Entry point for the Solace AI Event Connector"""

import threading
import queue
import traceback
import os
import pathlib

from datetime import datetime
from typing import List, Dict, Any
from .common.log import log, setup_log
from .common.utils import resolve_config_values
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
                app = App.create_from_flows(
                    flows=self.config.get("flows", []),
                    app_name=app_name,
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
                for index, app_config in enumerate(apps_config):
                    log.info("Creating app %s", app_config.get("name"))
                    num_instances = app_config.get("num_instances", 1)
                    if num_instances < 1:
                        num_instances = 1
                        log.warning(
                            "Number of instances for app %s is less than 1. Setting it to 1",
                            app_config.get("name"),
                        )

                    for i in range(num_instances):
                        app = App(
                            app_config=app_config,
                            app_index=index,
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

            # Run all apps
            for app in self.apps:
                app.run()

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
        app_config = {"name": app_name, "flows": flows}

        # Create the app
        app = App(
            app_config=app_config,
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
                for app in self.apps:
                    app.wait_for_flows()
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
        self.flows.clear()

        # Clean up queues
        for queue_name, queue in self.flow_input_queues.items():
            try:
                while not queue.empty():
                    queue.get_nowait()
            except Exception:
                log.error(f"Error cleaning queue {queue_name}")
        self.flow_input_queues.clear()

        if hasattr(self, "trace_queue") and self.trace_queue:
            self.trace_queue.put(None)  # Signal the trace thread to stop
        if self.trace_thread:
            self.trace_thread.join()
        if hasattr(self, "cache_check_thread"):
            self.cache_check_thread.join()
        if hasattr(self, "error_queue"):
            self.error_queue.put(None)

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

        # Create the trace file
        with open(trace_file, "a", encoding="utf-8") as f:
            while True:
                # Get the next trace message
                try:
                    trace_message = self.trace_queue.get(timeout=1)
                    # Write the trace message to the file with a timestamp
                    timestamp = datetime.now().isoformat()
                    f.write(f"{timestamp}: {trace_message}\n")
                    f.flush()

                except queue.Empty:
                    if self.stop_signal.is_set():
                        break
                    continue

    def validate_config(self):
        """Just some quick validation of the config for now"""
        if not self.config:
            raise ValueError("No config provided") from None

        # Check if either apps or flows are defined
        if not self.config.get("apps") and not self.config.get("flows"):
            raise ValueError("No apps or flows defined in configuration file") from None

        if not self.config.get("log"):
            log.warning("No log config provided - using defaults")

        # If apps are defined, validate them
        if self.config.get("apps"):
            for index, app in enumerate(self.config.get("apps", [])):
                if not app.get("name"):
                    raise ValueError(f"App name not provided in app {index}") from None

                if not app.get("flows"):
                    raise ValueError(
                        f"No flows defined in app {app.get('name')}"
                    ) from None

                # Validate flows in the app
                self._validate_flows(app.get("flows"), f"app {app.get('name')}")

        # If flows are defined at the top level (for backward compatibility), validate them
        if self.config.get("flows"):
            self._validate_flows(self.config.get("flows"), "top level")

    def _validate_flows(self, flows, context):
        """Validate flows configuration"""
        for index, flow in enumerate(flows):
            if not flow.get("name"):
                raise ValueError(
                    f"Flow name not provided in flow {index} of {context}"
                ) from None

            if not flow.get("components"):
                raise ValueError(
                    f"Flow components list not provided in flow {index} of {context}"
                ) from None

            # Verify that the components list is a list
            if not isinstance(flow.get("components"), list):
                raise ValueError(
                    f"Flow components is not a list in flow {index} of {context}"
                ) from None

            # Loop through the components and validate them
            for component_index, component in enumerate(flow.get("components", [])):
                if not component.get("component_name"):
                    raise ValueError(
                        f"component_name not provided in flow {index}, component {component_index} of {context}"
                    ) from None

                if not component.get("component_module"):
                    raise ValueError(
                        f"component_module not provided in flow {index}, "
                        f"component {component_index} of {context}"
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
        backend = create_storage_backend(backend_type)
        return CacheService(backend)

    def stop(self):
        """Stop the Solace AI Event Connector"""
        log.info("Stopping Solace AI Event Connector")
        self.stop_signal.set()

        # Stop core services first
        self.timer_manager.stop()  # Stop the timer manager first
        self.cache_service.stop()  # Stop the cache service

        if self.trace_thread:
            self.trace_thread.join()
