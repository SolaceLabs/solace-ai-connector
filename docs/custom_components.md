# Custom Components

## Purpose

Custom components provide a way to extend the functionality of the Solace AI Connector beyond what's possible with the built-in components and configuration options. Sometimes, it's easier and more efficient to add custom code than to build a complex configuration file, especially for specialized or unique processing requirements.

## Requirements of a Custom Component

To create a custom component, you need to follow these requirements:

1. **Inherit from ComponentBase**: Your custom component class should inherit from the `ComponentBase` class.

2. **Info Section**: Define an `info` dictionary with the following keys:
   - `class_name`: The name of your custom component class.
   - `config_parameters`: A list of dictionaries describing the configuration parameters for your component.
   - `input_schema`: A dictionary describing the expected input schema.
   - `output_schema`: A dictionary describing the expected output schema.

3. **Implement the `invoke` method**: This is the main method where your component's logic will be implemented.

Here's a basic template for a custom component:

```python
from solace_ai_connector.components.component_base import ComponentBase

info = {
    "class_name": "MyCustomComponent",
    "config_parameters": [
        {
            "name": "my_param",
            "type": "string",
            "required": True,
            "description": "A custom parameter"
        }
    ],
    "input_schema": {
        "type": "object",
        "properties": {
            "input_data": {"type": "string"}
        }
    },
    "output_schema": {
        "type": "object",
        "properties": {
            "output_data": {"type": "string"}
        }
    }
}

class MyCustomComponent(ComponentBase):
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        self.my_param = self.get_config("my_param")

    def invoke(self, message, data):
        # Your custom logic here
        result = f"{self.my_param}: {data['input_data']}"
        return {"output_data": result}
```

## Overrideable Methods

While the `invoke` method is the main one you'll implement, there are several other methods you can override to customize your component's behavior:

1. `invoke(self, message, data)`: The main processing method for your component.
2. `get_next_event(self)`: Customize how your component receives events.
3. `send_message(self, message)`: Customize how your component sends messages to the next component.
4. `handle_timer_event(self, timer_data)`: Handle timer events if your component uses timers.
5. `handle_cache_expiry_event(self, timer_data)`: Handle cache expiry events if your component uses the cache service.
6. `process_pre_invoke(self, message)`: Customize preprocessing before `invoke` is called.
7. `process_post_invoke(self, result, message)`: Customize postprocessing after `invoke` is called.

## Advanced Features

Custom components can take advantage of advanced features provided by the Solace AI Connector. These include:

- Broker request-response functionality
- Cache services
- Timer management

For more information on these advanced features and how to use them in your custom components, please refer to the [Advanced Component Features](advanced_component_features.md) documentation.

By creating custom components, you can extend the Solace AI Connector to meet your specific needs while still benefiting from the framework's built-in capabilities for event processing, flow management, and integration with Solace event brokers.

## Example

See the [Tips and Tricks page](tips_and_tricks.md) for an example of creating a custom component.


[]