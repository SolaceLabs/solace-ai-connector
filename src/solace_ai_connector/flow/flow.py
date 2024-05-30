"""Main class for the flow"""

# from solace_ai_connector.common.log import log
from ..common.utils import import_module


class Flow:
    def __init__(
        self,
        flow_config,
        flow_index,
        stop_signal,
        error_queue=None,
        instance_name=None,
        storage_manager=None,
        trace_queue=None,
        flow_instance_index=0,
        connector=None,
    ):
        self.flow_config = flow_config
        self.flow_index = flow_index
        self.component_groups = []
        self.name = flow_config.get("name")
        self.module_info = None
        self.stop_signal = stop_signal
        self.error_queue = error_queue
        self.instance_name = instance_name
        self.storage_manager = storage_manager
        self.trace_queue = trace_queue
        self.flow_instance_index = flow_instance_index
        self.connector = connector
        self.flow_input_queue = None
        self.threads = []
        self.create_components()

    def create_components(self):
        # Loop through the components and create them
        for index, component in enumerate(self.flow_config.get("components", [])):
            self.create_component_group(component, index)

        # Now loop through them again and set the next component
        for index, component_group in enumerate(self.component_groups):
            if index < len(self.component_groups) - 1:
                for component in component_group:
                    component.set_next_component(self.component_groups[index + 1][0])

        # Now one more time to create threads and run them
        for index, component_group in enumerate(self.component_groups):
            for component in component_group:
                thread = component.create_thread_and_run()
                self.threads.append(thread)

        self.flow_input_queue = self.component_groups[0][0].get_input_queue()

    def create_component_group(self, component, index):
        component_module = component.get("component_module", "")
        base_path = component.get("component_base_path", None)
        num_instances = component.get("num_instances", 1)
        # component_config = component.get("component_config", {})
        # component_name = component.get("component_name", "")

        # imported_module = import_from_directories(component_module)
        imported_module = import_module(component_module, base_path)

        try:
            self.module_info = getattr(imported_module, "info")
        except AttributeError as e:
            raise ValueError(
                f"Component module '{component_module}' does not have an 'info' attribute. It probably isn't a valid component."
            ) from e

        component_class = getattr(imported_module, self.module_info["class_name"])

        # Create the component
        component_group = []
        sibling_component = None
        for component_index in range(num_instances):
            component_instance = component_class(
                config=component,
                index=index,
                module_info=self.module_info,
                flow_name=self.name,
                stop_signal=self.stop_signal,
                sibling_component=sibling_component,
                component_index=component_index,
                error_queue=self.error_queue,
                instance_name=self.instance_name,
                storage_manager=self.storage_manager,
                trace_queue=self.trace_queue,
                connector=self.connector,
            )
            sibling_component = component_instance

            # Add the component to the list
            component_group.append(component_instance)

        # Add the component to the list
        self.component_groups.append(component_group)

    def get_flow_input_queue(self):
        return self.flow_input_queue

    def wait_for_threads(self):
        for thread in self.threads:
            thread.join()
