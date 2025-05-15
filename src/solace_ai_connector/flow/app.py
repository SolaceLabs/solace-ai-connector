"""App class for the Solace AI Event Connector"""

from typing import List, Dict, Any, Optional
import os

from ..common.log import log
from .flow import Flow


class App:
    """
    App class for the Solace AI Event Connector.
    An app is a collection of flows that are logically grouped together.
    """

    def __init__(
        self,
        app_config: Dict[str, Any],
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
            app_config: Configuration for the app
            app_index: Index of the app in the list of apps
            stop_signal: Signal to stop the app
            error_queue: Queue for error messages
            instance_name: Name of the connector instance
            trace_queue: Queue for trace messages
            connector: Reference to the parent connector
        """
        self.app_config = app_config
        self.app_index = app_index
        self.name = app_config.get("name", f"app_{app_index}")
        self.num_instances = app_config.get("num_instances", 1)
        self.flows: List[Flow] = []
        self.stop_signal = stop_signal
        self.error_queue = error_queue
        self.instance_name = instance_name
        self.trace_queue = trace_queue
        self.connector = connector
        self.flow_input_queues = {}

        # Create flows for this app
        self.create_flows()

    def create_flows(self):
        """Create flows for this app"""
        try:
            for index, flow in enumerate(self.app_config.get("flows", [])):
                log.info(f"Creating flow {flow.get('name')} in app {self.name}")
                num_instances = flow.get("num_instances", 1)
                if num_instances < 1:
                    num_instances = 1
                for i in range(num_instances):
                    flow_instance = self.create_flow(flow, index, i)
                    flow_input_queue = flow_instance.get_flow_input_queue()
                    self.flow_input_queues[flow.get("name")] = flow_input_queue
                    self.flows.append(flow_instance)
        except Exception:
            log.error(f"Error creating flows for app {self.name}")
            raise ValueError(
                f"Failed to create flows for app {self.name}. Check the configuration."
            ) from None

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
        for flow in self.flows:
            flow.run()

    def wait_for_flows(self):
        """Wait for all flows to complete"""
        for flow in self.flows:
            flow.wait_for_threads()

    def cleanup(self):
        """Clean up resources and ensure all threads are properly joined"""
        log.info(f"Cleaning up app: {self.name}")
        for flow in self.flows:
            try:
                flow.cleanup()
            except Exception:
                log.error(f"Error cleaning up flow in app {self.name}")
        self.flows.clear()
        self.flow_input_queues.clear()

    def get_config(self, key=None, default=None):
        """
        Get a configuration value from the app configuration.

        Args:
            key: Configuration key
            default: Default value if key is not found

        Returns:
            The configuration value or default
        """
        return self.app_config.get(key, default)

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
        app_config = {"name": app_name, "flows": flows}
        return cls(app_config=app_config, **kwargs)
