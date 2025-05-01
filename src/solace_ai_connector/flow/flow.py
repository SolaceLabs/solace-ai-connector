"""Main class for the flow"""

import threading
from typing import List

from ..components.component_base import ComponentBase
from ..common.log import log
from ..common.utils import import_module


class FlowLockManager:

    def __init__(self):
        self._lock = threading.Lock()
        self.locks = {}

    def get_lock(self, lock_name):
        with self._lock:
            if lock_name not in self.locks:
                self.locks[lock_name] = threading.Lock()

            return self.locks[lock_name]


class FlowKVStore:

    def __init__(self):
        self.store = {}

    def set(self, key, value):
        self.store[key] = value

    def get(self, key):
        return self.store.get(key, None)


class Flow:

    _lock_manager = FlowLockManager()
    _kv_store = FlowKVStore()

    def __init__(
        self,
        flow_config,
        flow_index,
        stop_signal,
        error_queue=None,
        instance_name=None,
        trace_queue=None,
        flow_instance_index=0,
        connector=None,
        app=None,
    ):
        self.flow_config = flow_config
        self.flow_index = flow_index
        self.component_groups: List[List[ComponentBase]] = []
        self.name = flow_config.get("name")
        self.module_info = None
        self.stop_signal = stop_signal
        self.instance_name = instance_name
        self.trace_queue = trace_queue
        self.flow_instance_index = flow_instance_index
        self.connector = connector
        self.app = app
        self.flow_input_queue = None
        self.threads = []
        self.flow_lock_manager = Flow._lock_manager
        self.flow_kv_store = Flow._kv_store
        self.cache_service = connector.cache_service if connector else None
        self.error_queue = error_queue
        self.put_errors_in_error_queue = flow_config.get(
            "put_errors_in_error_queue", True
        )

        self.create_components()

    def get_input_queue(self):
        return self.flow_input_queue

    def create_components(self):
        # Loop through the components and create them
        for index, component in enumerate(self.flow_config.get("components", [])):
            self.create_component_group(component, index)

        # Now loop through them again and set the next component
        for index, component_group in enumerate(self.component_groups):
            if index < len(self.component_groups) - 1:
                for component in component_group:
                    component.set_next_component(self.component_groups[index + 1][0])

        if (
            self.component_groups
            and len(self.component_groups[0]) > 0
            and self.component_groups[0][0]
        ):
            self.flow_input_queue = self.component_groups[0][0].get_input_queue()
        else:
            log.error(f"No components created for flow {self.name}")
            raise ValueError(f"No components created for flow {self.name}") from None

    def run(self):
        # Now one more time to create threads and run them
        for _index, component_group in enumerate(self.component_groups):
            for component in component_group:
                thread = component.create_thread_and_run()
                self.threads.append(thread)

    def create_component_group(self, component, index):
        component_module = component.get("component_module", "")
        base_path = component.get("component_base_path", None)
        component_package = component.get("component_package", None)
        num_instances = component.get("num_instances", 1)
        disabled = component.get("disabled", False)
        if disabled:
            log.warning(
                f"Component '{component.get('component_name')}' is disabled and will not be created."
            )
            return

        imported_module = import_module(component_module, base_path, component_package)

        try:
            self.module_info = getattr(imported_module, "info")
        except AttributeError:
            raise ValueError(
                f"Component module '{component_module}' does not have an 'info' attribute. It probably isn't a valid component."
            ) from None

        component_class = getattr(imported_module, self.module_info["class_name"])

        # Create the component
        component_group = []
        sibling_component = None
        for component_index in range(num_instances):
            component_instance = component_class(
                config=component,
                index=index,
                flow_name=self.name,
                flow_lock_manager=self.flow_lock_manager,
                flow_kv_store=self.flow_kv_store,
                stop_signal=self.stop_signal,
                sibling_component=sibling_component,
                component_index=component_index,
                error_queue=self.error_queue,
                instance_name=self.instance_name,
                trace_queue=self.trace_queue,
                connector=self.connector,
                timer_manager=self.connector.timer_manager if self.connector else None,
                cache_service=self.cache_service,
                put_errors_in_error_queue=self.put_errors_in_error_queue,
                app=self.app,
            )
            sibling_component = component_instance

            # Add the component to the list
            component_group.append(component_instance)

        # Add the component to the list
        self.component_groups.append(component_group)

    def get_flow_input_queue(self):
        return self.flow_input_queue

    # This will set the next component in all the components in the
    # last component group
    def set_next_component(self, component):
        for comp in self.component_groups[-1]:
            comp.set_next_component(component)

    def wait_for_threads(self):
        for thread in self.threads:
            thread.join()

    def cleanup(self):
        """Clean up resources and ensure all threads are properly joined"""
        log.info("Cleaning up flow: %s", self.name)
        for component_group in self.component_groups:
            for component in component_group:
                component.cleanup()
        self.component_groups.clear()
        self.threads.clear()

    def get_app(self):
        """Get the app that this flow belongs to"""
        return self.app
