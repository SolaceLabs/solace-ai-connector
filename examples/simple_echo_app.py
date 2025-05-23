"""
Example of a Simplified App defined entirely within a single Python file,
using a custom App subclass.

This app listens on a Solace queue, logs the received message payload,
and echoes the payload back to a predefined topic.
"""

import os
import time
from typing import Any
from solace_ai_connector.components.component_base import ComponentBase
from solace_ai_connector.common.log import log, setup_log
from solace_ai_connector.common.message import Message
from solace_ai_connector.flow.app import App  # Import the base App class

# --- 1. Define the Component ---

# Component Information (required by ComponentBase)
component_info = {
    "class_name": "SimpleEchoComponent",
    "description": "A simple component that logs the input payload and echoes it back.",
    "short_description": "Logs and echoes input payload.",
    "config_parameters": [
        {
            "name": "echo_topic",
            "required": True,
            "description": "The topic to publish the echoed message to.",
            "type": "string",
            "default": "echo/output",
        },
        {
            "name": "log_prefix",
            "required": False,
            "description": "Prefix for log messages.",
            "type": "string",
            "default": "ECHO:",
        },
    ],
    "input_schema": {
        "type": "any",
        "description": "Accepts any input payload.",
    },
    "output_schema": {
        "type": "object",
        "properties": {
            "payload": {"type": "any", "description": "The original input payload."},
            "topic": {"type": "string", "description": "The configured echo topic."},
            "user_properties": {
                "type": "object",
                "description": "Original user properties plus an echo timestamp.",
            },
        },
    },
}


# The Component Class
class SimpleEchoComponent(ComponentBase):
    def __init__(self, **kwargs):
        # Pass the component_info dictionary to the base class
        super().__init__(component_info, **kwargs)
        self.echo_topic = self.get_config("echo_topic")
        self.log_prefix = self.get_config("log_prefix")
        log.info(
            f"{self.log_identifier} SimpleEchoComponent initialized. Echoing to topic: {self.echo_topic}"
        )

    def invoke(self, message: Message, data: Any) -> dict:
        """
        Logs the input data and prepares the output message.

        Args:
            message: The input Message object.
            data: The input data extracted based on 'input_selection' (defaults to message.previous).
                  In this simplified app, it will be the direct output of BrokerInput.

        Returns:
            A dictionary conforming to the BrokerOutput input schema.
        """
        # 'data' here will contain {'payload': ..., 'topic': ..., 'user_properties': ...}
        # from the implicit BrokerInput component.
        input_payload = data.get("payload")
        input_topic = data.get("topic")
        input_user_props = data.get("user_properties", {})

        log.info(
            f"{self.log_identifier} {self.log_prefix} Received payload from topic '{input_topic}': {input_payload}"
        )

        # Prepare output user properties, adding an echo timestamp
        output_user_props = input_user_props.copy()
        output_user_props["echo_timestamp"] = time.time()

        # Return the structure expected by the implicit BrokerOutput
        return {
            "payload": input_payload,  # Echo the original payload
            "topic": self.echo_topic,
            "user_properties": output_user_props,
        }


# --- 2. Define the Custom App Class ---

# Info dictionary for the App class itself
info = {
    "class_name": "SimpleEchoApp",
    "description": "A simplified echo application defined entirely in code.",
    "short_description": "Code-based echo app.",
}


class SimpleEchoApp(App):
    """
    Custom App class that defines its configuration internally.
    """

    # Define the entire app configuration as a class attribute or within __init__
    app_config = {
        "name": "simple_echo_app_from_code",  # Internal name, can be overridden by YAML 'name'
        "broker": {
            # Use environment variables or replace with actual values
            "broker_type": os.getenv("SOLACE_BROKER_TYPE", "solace"),
            "broker_url": os.getenv("SOLACE_URL", "ws://localhost:8080"),
            "broker_vpn": os.getenv("SOLACE_VPN", "default"),
            "broker_username": os.getenv("SOLACE_USERNAME", "user"),
            "broker_password": os.getenv("SOLACE_PASSWORD", "password"),
            "input_enabled": True,
            "output_enabled": True,  # Required for echoing
            "request_reply_enabled": False,
            "queue_name": "q/simple_echo_app/input",
            "create_queue_on_start": True,
            "payload_format": "json",  # Assume input/output is JSON
            "payload_encoding": "utf-8",
        },
        "app_config": {
            # Optional app-level config accessible via component.get_config('app_param')
            "app_param": "global_app_value"
        },
        "components": [
            {
                "name": "echo_processor",
                # Directly pass the component class defined in this file.
                # This avoids using __name__ and is clearer when components
                # are defined locally within the App's module.
                "component_class": SimpleEchoComponent,
                # component_module is ignored if component_class is provided.
                "component_config": {
                    # Configuration specific to SimpleEchoComponent
                    "echo_topic": "echo/output/from_code",
                    "log_prefix": "CODE_ECHO:",
                },
                "subscriptions": [
                    # The topic subscription for the implicit BrokerInput queue
                    {"topic": "echo/input/>"}
                ],
                # Define input selection for the component (optional, defaults shown)
                # This tells the component what data to receive from the previous step.
                # For the first component after BrokerInput/Router, 'previous' holds
                # the output of BrokerInput.
                "input_selection": {"source_expression": "previous"},
            }
        ],
    }

    def __init__(self, app_info: dict, **kwargs):
        """
        Initialize the custom App.

        Args:
            app_info (dict): Configuration passed from the main connector (e.g., from YAML).
                             This implementation ignores it and uses its internal config.
            **kwargs: Other arguments passed by the connector (stop_signal, etc.)
        """
        # Override the passed app_info with the internally defined configuration.
        # Merge the name from the YAML config if provided, otherwise use internal name.
        merged_app_info = self.app_config.copy()
        if app_info and "name" in app_info:
            merged_app_info["name"] = app_info["name"]

        # Call the base class constructor with our defined configuration
        super().__init__(app_info=merged_app_info, **kwargs)
        log.info(f"Initialized SimpleEchoApp '{self.name}' from code definition.")


# --- 3. Framework Integration (Conceptual) ---
# The Solace AI Connector framework loads this app by specifying its module
# in the main configuration file (e.g., config.yaml):
#
# apps:
#   - name: my_echo_instance # Name for this specific instance
#     app_module: examples.simple_echo_app # Points to this file
#     # Optional: Override specific app-level config here if needed
#     # config:
#     #   app_param: "override_value"

# Example of how this *might* be run if the framework supports loading Python app configs.
# (This requires the main connector logic to be adapted).
if __name__ == "__main__":
    # This is for demonstration purposes ONLY.
    # Running the connector usually happens via the main entry point (main.py).
    print("Running Simple Echo App (Conceptual Standalone Execution)")

    # Configure basic logging for the example
    setup_log(
        logFilePath="simple_echo_app.log",
        stdOutLogLevel="INFO",
        fileLogLevel="DEBUG",
        logFormat="pipe-delimited",
        logBack=None,
    )

    try:
        # Dynamically import the connector - adjust path if necessary
        from solace_ai_connector.solace_ai_connector import SolaceAiConnector

        # Simulate how the main connector might load this config via app_module
        # The actual APP_CONFIG is now inside the SimpleEchoApp class.
        connector_config = {
            "log": {  # Basic logging config for the connector itself
                "stdout_log_level": "INFO",
                "log_file_level": "DEBUG",
                "log_file": "connector_main.log",
            },
            "apps": [
                {
                    "name": "simple_echo_instance_main",  # Instance name from YAML
                    "app_module": __name__,  # Point to this module
                }
            ],
        }

        connector = SolaceAiConnector(config=connector_config)
        connector.run()

        log.info(
            "Simple Echo App started. Waiting for messages on queue 'q/simple_echo_app/input' matching 'echo/input/>'. Press Ctrl+C to stop."
        )

        # Keep the main thread alive
        while True:
            time.sleep(5)

    except ImportError as e:
        print(
            f"Error: Could not import SolaceAiConnector. Make sure it's installed and accessible."
        )
        print(e)
    except KeyboardInterrupt:
        log.info("Ctrl+C received. Stopping the connector.")
        if "connector" in locals():
            connector.stop()
    except Exception as e:
        log.error(f"An unexpected error occurred: {e}", exc_info=True)
    finally:
        if "connector" in locals():
            log.info("Cleaning up connector resources.")
            connector.cleanup()
        log.info("Simple Echo App finished.")
