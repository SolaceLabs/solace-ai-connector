"""
Component to route messages to different components based on topic subscriptions
within a simplified app flow.
"""

import re
from typing import List, Tuple, Pattern, Any

from ..components.component_base import ComponentBase
from ..common.log import log
from ..common.message import Message
from ..common.event import Event, EventType
from ..common import Message_NACK_Outcome  # Import the missing name

# Define the component information
info = {
    "class_name": "SubscriptionRouter",
    "description": (
        "Internal component for simplified apps. Routes incoming messages from a "
        "single queue to the appropriate user-defined component based on topic "
        "subscriptions defined in the app configuration. Uses the first matching "
        "subscription found in the component list order."
    ),
    "short_description": "Routes messages based on topic subscriptions (internal).",
    "config_parameters": [
        {
            "name": "app_components_config_ref",
            "required": True,
            "description": "Reference to the original list of user component configurations from the simplified app definition.",
            "type": "list",
        },
    ],
    "input_schema": {
        "type": "object",
        "properties": {
            "payload": {"type": "any"},
            "topic": {"type": "string"},
            "user_properties": {"type": "object"},
        },
        "required": ["topic"],
    },
    "output_schema": None,  # This component does not produce output itself
}


class SubscriptionRouter(ComponentBase):
    """
    Routes messages based on topic subscriptions defined in simplified app components.
    """

    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        # List storing tuples: (target_component_instance, list_of_compiled_regex)
        self.component_targets: List[Tuple[ComponentBase, List[Pattern]]] = []
        self._build_targets()

    def _build_targets(self):
        """
        Builds the list of target components and their compiled subscription regex patterns.
        """
        # Get the original component configurations from the app definition
        app_components_config = self.get_config("app_components_config_ref")
        if not app_components_config or not isinstance(app_components_config, list):
            log.error(
                "%s Invalid or missing 'app_components_config_ref'. Cannot build routing targets.",
                self.log_identifier,
            )
            return

        # Get the actual instantiated component groups from the flow
        # Assuming this router is part of the first (and likely only) flow in the simplified app
        try:
            # Access the flow this component belongs to via the parent app
            flow = self.get_app().flows[0]
            flow_component_groups = flow.component_groups
        except (AttributeError, IndexError):
            log.error(
                "%s Could not access flow component groups. Cannot build routing targets.",
                self.log_identifier,
            )
            return

        # Map component names from config to their instantiated objects in the flow
        # This mapping needs to account for the position of BrokerInput and the Router itself
        component_map = {}
        # Start index in flow_component_groups depends on whether BrokerInput exists
        start_index = 0
        if (
            flow_component_groups
            and flow_component_groups[0][0].module_info.get("class_name")
            == "BrokerInput"
        ):
            start_index = 1  # Skip BrokerInput
        # Skip self (SubscriptionRouter) if present
        if (
            flow_component_groups
            and len(flow_component_groups) > start_index
            and flow_component_groups[start_index][0].module_info.get("class_name")
            == "SubscriptionRouter"
        ):
            start_index += 1

        # Map remaining components based on order
        config_idx = 0
        flow_idx = start_index
        while config_idx < len(app_components_config) and flow_idx < len(
            flow_component_groups
        ):
            comp_config = app_components_config[config_idx]
            comp_name = comp_config.get("name")
            # Get the first instance from the component group for routing purposes
            component_instance = flow_component_groups[flow_idx][0]
            component_map[comp_name] = component_instance
            config_idx += 1
            flow_idx += 1

        if config_idx != len(app_components_config):
            log.warning(
                "%s Mismatch between configured components and flow components during routing target build.",
                self.log_identifier,
            )

        # Build the targets list with compiled regex
        for comp_config in app_components_config:
            comp_name = comp_config.get("name")
            component_instance = component_map.get(comp_name)
            if not component_instance:
                log.warning(
                    "%s Could not find instance for component '%s' during routing target build. Skipping.",
                    self.log_identifier,
                    comp_name,
                )
                continue

            subscriptions = comp_config.get("subscriptions", [])
            regex_list: List[Pattern] = []
            for sub in subscriptions:
                topic = sub.get("topic")
                if topic:
                    # Convert Solace wildcard topic to regex
                    # Replace '>' at the end of a segment or string
                    regex_str = re.sub(r"(?:/|^)>$", "/.*", topic)
                    # Replace '*' within a segment
                    regex_str = regex_str.replace("*", "[^/]+")
                    # Anchor the regex
                    regex_str = f"^{regex_str}$"
                    try:
                        regex_list.append(re.compile(regex_str))
                    except re.error as e:
                        log.error(
                            "%s Invalid regex generated from subscription '%s' for component '%s': %s",
                            self.log_identifier,
                            topic,
                            comp_name,
                            e,
                        )

            if regex_list:
                self.component_targets.append((component_instance, regex_list))
                log.debug(
                    "%s Added target: Component '%s', Subscriptions: %s",
                    self.log_identifier,
                    comp_name,
                    [r.pattern for r in regex_list],
                )
            else:
                log.debug(
                    "%s Component '%s' has no subscriptions defined for routing.",
                    self.log_identifier,
                    comp_name,
                )

    def invoke(self, message: Message, data: Any):
        """
        Receives a message, finds the first matching component based on topic,
        and enqueues the event to that component.
        """
        msg_topic = message.get_topic()
        if not msg_topic:
            log.warning(
                "%s Message has no topic, cannot route. Discarding.",
                self.log_identifier,
            )
            self.discard_current_message()  # Discard if unroutable - ACK will be called
            return None

        log.debug(
            "%s Attempting to route message with topic: '%s'",
            self.log_identifier,
            msg_topic,
        )

        for target_component, regex_list in self.component_targets:
            for regex_pattern in regex_list:
                if regex_pattern.match(msg_topic):
                    # Found target, enqueue the original Event to the component's input queue
                    log.info(
                        "%s Routing message with topic '%s' to component '%s'",
                        self.log_identifier,
                        msg_topic,
                        target_component.name,
                    )
                    try:
                        # Re-wrap the message in an Event object to pass to the target
                        original_event = Event(EventType.MESSAGE, message)
                        target_component.enqueue(original_event)
                        # DO NOT discard the message here. Returning None prevents
                        # ComponentBase from calling process_post_invoke, and
                        # since discard_current_message was not called, the
                        # original acknowledgements remain intact on the message
                        # and will be called by the target component later.
                        return None
                    except Exception as e:
                        log.error(
                            "%s Error enqueuing message to component '%s': %s",
                            self.log_identifier,
                            target_component.name,
                            e,
                            exc_info=True,
                        )
                        # Let error handling proceed (ComponentBase will NACK original message)
                        raise e

        log.warning(
            "%s No matching subscription found for topic '%s'. Discarding message.",
            self.log_identifier,
            msg_topic,
        )
        self.discard_current_message()  # Discard if unroutable - ACK will be called
        return None

    def get_negative_acknowledgement_callback(self):
        """This component doesn't originate messages, so no NACK needed."""
        return None

    def nack_reaction_to_exception(self, exception_type):
        """Default NACK reaction."""
        return Message_NACK_Outcome.REJECTED
