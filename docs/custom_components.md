# Custom Components

## Purpose

Custom components provide a way to extend the functionality of the Solace AI Connector beyond what's possible with the built-in components and configuration options. Sometimes, it's easier and more efficient to add custom code than to build a complex configuration file, especially for specialized or unique processing requirements.

## Requirements of a Custom Component

To create a custom component, you need to follow these requirements:

1. **Inherit from ComponentBase**: Your custom component class should inherit from the `ComponentBase` class (`solace_ai_connector.components.component_base.ComponentBase`).

2. **Info Section**: Define an `info` dictionary (typically as a module-level variable or class attribute) with the following keys:
   - `class_name`: The name of your custom component class.
   - `config_parameters`: A list of dictionaries describing the configuration parameters for your component (used for validation and documentation). Each dictionary should include `name`, `description`, `type`, `required` (boolean, optional, default `False`), and `default` (optional).
   - `input_schema`: A dictionary describing the expected input schema for the `data` argument passed to the `invoke` method (using JSON Schema format).
   - `output_schema`: A dictionary describing the expected output schema for the value returned by the `invoke` method (using JSON Schema format).

3. **Implement `__init__`**: Your constructor must call `super().__init__(info, **kwargs)`. Access configuration parameters using `self.get_config()` *after* the superclass constructor is called.

4. **Implement the `invoke` method**: This is the main method where your component's core processing logic resides. It receives the `message` object and the selected `data` as input and should return the processed result (or `None` to stop processing).

Here's a basic template for a custom component:

```python
# my_custom_component.py
from solace_ai_connector.components.component_base import ComponentBase
from solace_ai_connector.common.message import Message
from solace_ai_connector.common.log import log
from typing import Any

# Define component information
info = {
    "class_name": "MyCustomComponent",
    "description": "A simple custom component example.",
    "config_parameters": [
        {
            "name": "my_param",
            "type": "string",
            "required": True,
            "description": "A custom parameter required by this component."
        },
        {
            "name": "optional_param",
            "type": "integer",
            "required": False,
            "default": 10,
            "description": "An optional parameter with a default value."
        }
    ],
    "input_schema": {
        "type": "object",
        "properties": {
            "input_data": {"type": "string"}
        },
        "required": ["input_data"] # Specifies 'input_data' must be in the 'data' passed to invoke
    },
    "output_schema": {
        "type": "object",
        "properties": {
            "output_data": {"type": "string"},
            "original_input": {"type": "string"}
        }
    }
}

class MyCustomComponent(ComponentBase):
    def __init__(self, **kwargs):
        # Pass the info dictionary to the base class constructor
        super().__init__(info, **kwargs)
        # Access validated config parameters AFTER super().__init__()
        self.my_param = self.get_config("my_param")
        self.optional_param = self.get_config("optional_param")
        log.info("%s Initialized with my_param='%s', optional_param=%d",
                 self.log_identifier, self.my_param, self.optional_param)

    def invoke(self, message: Message, data: Any) -> Any:
        """
        Processes the input data.
        Args:
            message: The full Message object.
            data: The input data selected by input_selection/transforms, matching input_schema.
        Returns:
            A dictionary matching the output_schema, or None.
        """
        input_text = data.get("input_data", "") # Safely get input
        log.debug("%s Received input: '%s'", self.log_identifier, input_text)

        # --- Custom Logic ---
        processed_result = f"{self.my_param}: {input_text} (opt: {self.optional_param})"
        # --- End Custom Logic ---

        # Return data matching the output_schema
        return {
            "output_data": processed_result,
            "original_input": input_text
        }

```

## Overrideable Methods

While the `invoke` method is the main one you'll implement, there are several other methods from `ComponentBase` you can override to customize your component's behavior:

1. `invoke(self, message, data)`: The main processing method for your component.
2. `get_next_event(self)`: Customize how your component receives events (primarily for input components).
3. `send_message(self, message)`: Customize how your component sends messages to the next component (primarily for output components or complex routing).
4. `handle_timer_event(self, timer_data)`: Handle timer events if your component uses timers via `self.add_timer()`.
5. `handle_cache_expiry_event(self, cache_data)`: Handle cache expiry events if your component uses the cache service with expiry.
6. `process_pre_invoke(self, message)`: Customize preprocessing before `invoke` is called (rarely needed, transforms are preferred).
7. `process_post_invoke(self, result, message)`: Customize postprocessing after `invoke` is called (rarely needed).
8. `get_acknowledgement_callback(self)`: Provide an ACK callback (for input components).
9. `get_negative_acknowledgement_callback(self)`: Provide a NACK callback (for input components).
10. `nack_reaction_to_exception(self, exception_type)`: Determine NACK outcome based on exception type.
11. `stop_component(self)`: Perform cleanup when the component is stopped.
12. `get_metrics(self)`: Return performance metrics.
13. `flush_metrics(self)`: Reset metrics if needed.

## Advanced Features

Custom components can take advantage of advanced features provided by the Solace AI Connector framework. These include:

- **Broker Request-Response:** Use `self.do_broker_request_response()` to interact synchronously with services via the broker (requires app-level configuration).
- **Cache Service:** Use `self.cache_service` (`add_data`, `get_data`, `remove_data`) for temporary data storage with optional expiry.
- **Timer Management:** Use `self.add_timer()` and `self.cancel_timer()` to schedule actions, handled in `handle_timer_event()`.
- **App-Level Configuration:** Access shared configuration defined in the parent app's `app_config:` block using `self.get_config()`.
- **Logging:** Use the standard Python `logging` module via `from solace_ai_connector.common.log import log`. Use `self.log_identifier` for context.

For more information on these advanced features and how to use them in your custom components, please refer to the [Advanced Component Features](advanced_component_features.md) documentation.

## Custom Apps and Validation

Similar to how custom components define an `info` dictionary for configuration and validation, custom *Apps* (subclasses of `solace_ai_connector.flow.app.App`) can define an `app_schema` class attribute. This allows you to specify required parameters and defaults for the app-level `app_config:` block in your YAML, enabling validation during app initialization. See the [App-Level Configuration and Validation](configuration.md#app-level-configuration-app_config-and-validation-app_schema) section in the configuration documentation for details.

By creating custom components (and potentially custom Apps), you can extend the Solace AI Connector to meet your specific needs while still benefiting from the framework's built-in capabilities for event processing, flow management, and integration with Solace event brokers.

## Example

See the [Tips and Tricks page](tips_and_tricks.md#using-custom-modules-with-the-ai-connector) for an example of creating and using a custom component.
```

docs/simplified-apps.md
