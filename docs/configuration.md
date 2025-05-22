# Configuration for the AI Event Connector

Table of Contents

- [Configuration for the AI Event Connector](#configuration-for-the-ai-event-connector)
  - [Configuration File Format and Rules](#configuration-file-format-and-rules)
    - [Special values](#special-values)
  - [Configuration File Structure](#configuration-file-structure)
    - [Log Configuration](#log-configuration)
    - [Trace Configuration](#trace-configuration)
    - [Shared Configurations](#shared-configurations)
    - [Apps Configuration](#apps-configuration)
      - [Standard App Configuration](#standard-app-configuration)
      - [Simplified App Configuration](#simplified-app-configuration)
      - [Simplified App: `broker` Configuration](#simplified-app-broker-configuration)
      - [Simplified App: `components` Configuration](#simplified-app-components-configuration)
      - [App-Level Configuration (`app_config`) and Validation (`app_schema`)](#app-level-configuration-app_config-and-validation-app_schema)
    - [Flow Configuration (Standard Apps)](#flow-configuration-standard-apps)
  - [Message Data](#message-data)
  - [Expression Syntax](#expression-syntax)
    - [Templates](#templates)
  - [Component Configuration](#component-configuration)
    - [component\_module](#component_module)
    - [component\_class](#component_class)
    - [component\_config](#component_config)
    - [input\_transforms](#input_transforms)
    - [input\_selection](#input_selection)
    - [queue\_depth](#queue_depth)
    - [num\_instances](#num_instances)
    - [subscriptions (Simplified Apps)](#subscriptions-simplified-apps)
    - [Built-in components](#built-in-components)
  - [Invoke Keyword](#invoke-keyword)
    - [Invoke with custom function](#invoke-with-custom-function)
    - [invoke\_functions](#invoke_functions)
    - [evaluate\_expression()](#evaluate_expression)
    - [user\_processor Component and invoke](#user_processor-component-and-invoke)
  - [Usecase Examples](#usecase-examples)

The AI Event Connector is highly configurable. You can define the apps, components of each flow, the queue depths between them, and the number of instances of each component. The configuration is done through a YAML file that is loaded when the connector starts. This allows you to easily change the configuration without having to modify the code.

## Configuration File Format and Rules

The configuration file is a YAML file that is loaded when the connector starts. Multiple YAML files can be passed to the connector at startup. The files will be merged, the latest file will overwrite the previous duplicate keys. Arrays will be concatenated. Useful to separate flows.

For example, if you have two files:

```bash
python3 -m solace_ai_connector.main config1.yaml config2.yaml
```

Since this application usings `pyyaml`, it is possible to use the `!include` directive to include the template from a file. This can be useful for very large templates or for templates that are shared across multiple components.

### Special values

Within the configuration, you can have simple static values, environment variables, or dynamic values using the `invoke` keyword.

- ***Environment Variables***

You can use environment variables in the configuration file by using the `${}` syntax. For example, if you have an environment variable `MY_VAR` you can use it in the configuration file like this:

```yaml
my_key: ${MY_VAR}
```
You can also provide default values: `${MY_VAR, default_value}`.

- ***Dynamic Values (invoke keyword)***

You can use dynamic values in the configuration file by using the `invoke` keyword. This allows you to do such things as import a module, instantiate a class and call a function to get the value. For example, if you want to get the operating system type you can use it in the configuration file like this:

```yaml
os_type:
  invoke:
    module: platform
    function: system
```

More details [here](#invoke-keyword).

## Configuration File Structure

The configuration file is a YAML file with these top-level keys:

- `log`: Configuration of logging for the connector
- `trace`: Configuration of tracing for the connector
- `shared_config`: Named configurations that can be used by multiple components later in the file
- `apps`: A list of app configurations, each containing flows or defining a simplified app.
- `flows`: A list of flow configurations (for backward compatibility, ignored if `apps` is present).

### Log Configuration

The `log` configuration section is used to configure the logging for the connector. It configures the logging behavior for stdout and file logs. It has the following keys:

- `stdout_log_level`: <DEBUG|INFO|WARNING|ERROR|CRITICAL> - The log level for the stdout log
- `log_file_level`: <DEBUG|INFO|WARNING|ERROR|CRITICAL> - The log level for the file log
- `log_file`: <string> - The file to log to. If not specified, no file logging will be done

Here is an example of a log configuration:

```yaml
log:
  stdout_log_level: INFO
  log_file_level: DEBUG
  log_file: /var/log/ai_event_connector.log
```

### Trace Configuration

The trace option will output logs to a trace log that has all the detail of the message at each point. It gives an output when a message is pulled out of an input queue and another one before invoke is called (i.e. after transforms).

```yaml
trace:
  trace_file: /var/log/ai_event_connector_trace.log
```

### Shared Configurations

The `shared_config` section is used to define configurations that can be used by multiple components later in the file. It is a dictionary of named configurations. Each named configuration is a dictionary of configuration values. Here is an example of a shared configuration:

```yaml
shared_config:
  my_shared_config: &my_shared_config
    my_key: my_value
    my_other_key: my_other_value
```

Later in the file, you can reference this shared configuration like this:

```yaml
  - my_component:
      <<: *my_shared_config
      my_key: my_new_value
```

### Apps Configuration

The `apps` section is a list of app configurations. An app is a logical grouping of functionality. Each app configuration is a dictionary.

There are two ways to define an app:

1.  **Standard App:** Defines explicit `flows`. This is the traditional way and offers maximum flexibility.
2.  **Simplified App:** Defines `broker` interactions and `components` directly, omitting `flows`. The framework generates the flow automatically. Ideal for simpler use cases. See [Simplified App Mode](simplified-apps.md) for details.

#### Standard App Configuration

A standard app configuration requires the following keys:

- `name`: <string> - The unique name of the app.
- `num_instances`: <int> - The number of instances of the app to run (optional, default is 1). Each instance runs independently.
- `flows`: A list of flow configurations. Check [Flow Configuration (Standard Apps)](#flow-configuration-standard-apps) for more details.
- `app_config`: <dictionary> - Optional app-level configuration accessible by components within this app via `self.get_config()`. See [App-Level Configuration (`app_config`) and Validation (`app_schema`)](#app-level-configuration-app_config-and-validation-app_schema).

```yaml
apps:
  - name: my_standard_app
    num_instances: 1
    app_config: # This is the app-level config block
      global_threshold: 50
      api_key: ${MY_API_KEY}
    flows:
      - name: my_explicit_flow
        components:
          - component_name: my_component
            # ... component details ...
            # This component can access 'global_threshold' via self.get_config('global_threshold')
  - name: another_standard_app
    flows:
      - name: another_explicit_flow
        components:
          - component_name: another_component
            # ... component details ...
```

#### Simplified App Configuration

A simplified app configuration **omits** the `flows` key and instead defines broker interactions and processing components directly. See the [Simplified App Mode documentation](simplified-apps.md) for a comprehensive explanation.

It requires the following keys:

- `name`: <string> - The unique name of the app.
- `num_instances`: <int> - The number of instances of the app definition to run (optional, default is 1). Note: This scales the entire app definition, including broker connections. For scaling only processing logic, use `num_instances` at the component level.
- `broker`: <dictionary> - Defines how the app interacts with the Solace broker. See [Simplified App: `broker` Configuration](#simplified-app-broker-configuration).
- `components`: <list> - Defines the processing logic components. See [Simplified App: `components` Configuration](#simplified-app-components-configuration).
- `app_config`: <dictionary> - Optional app-level configuration accessible by components within this app via `self.get_config()`. See [App-Level Configuration (`app_config`) and Validation (`app_schema`)](#app-level-configuration-app_config-and-validation-app_schema).

```yaml
apps:
  - name: my_simplified_app
    broker:
      # ... broker details ...
      input_enabled: true
      output_enabled: true
      queue_name: "q/my_simple_app/input"
    app_config: # This is the app-level config block
      api_key: ${MY_API_KEY}
      default_model: "gpt-4o"
    components:
      - name: processor
        component_module: my_processor
        subscriptions:
          - topic: "data/input/>"
        # ... other component details ...
        # This component can access 'api_key' via self.get_config('api_key')
```

#### Simplified App: `broker` Configuration

This section defines how the simplified app interacts with the Solace broker. The framework uses these settings to create implicit `BrokerInput`, `BrokerOutput`, and `RequestResponseFlowController` components.

- **Connection Details (Required):**
    - `broker_type`: <string> - `solace` or `dev_broker`.
    - `broker_url`: <string> - Broker URL (e.g., `ws://host:port`).
    - `broker_vpn`: <string> - Broker VPN name.
    - `broker_username`: <string> - Client username.
    - `broker_password`: <string> - Client password.
- **Connection Details (Optional):**
    - `trust_store_path`: <string> - Path to trust store for TLS.
    - `reconnection_strategy`: <string> - `forever_retry` (default) or `parametrized_retry`.
    - `retry_interval`: <int> - Milliseconds between retries (default: 10000).
    - `retry_count`: <int> - Number of retries if `parametrized_retry` (default: 10).
- **Interaction Flags:**
    - `input_enabled`: <boolean> - **Required.** Must be `true` to receive messages. Creates implicit `BrokerInput`.
    - `output_enabled`: <boolean> - Optional (default `false`). Set `true` to enable sending messages. Creates implicit `BrokerOutput`.
    - `request_reply_enabled`: <boolean> - Optional (default `false`). Set `true` to enable `self.do_broker_request_response()`. Creates implicit `RequestResponseFlowController`.
- **Input Configuration (Required if `input_enabled: true`):**
    - `queue_name`: <string> - The single, dedicated queue this app instance listens on.
- **Input Configuration (Optional):**
    - `create_queue_on_start`: <boolean> - Default `true`. Attempts to create the queue via the data connection.
    - `payload_encoding`: <string> - Default `utf-8`. How to decode incoming payloads (`utf-8`, `base64`, `gzip`, `none`).
    - `payload_format`: <string> - Default `json`. How to parse decoded payloads (`json`, `yaml`, `text`).
    - `max_redelivery_count`: <int> - Sets broker redelivery attempts (if supported).
- **Output Configuration (Optional, relevant if `output_enabled: true`):**
    - `payload_encoding`: <string> - Default `utf-8`. How to encode outgoing payloads.
    - `payload_format`: <string> - Default `json`. How to format outgoing payloads before encoding.
    - `propagate_acknowledgements`: <boolean> - Default `true`. Whether broker publish confirmation should trigger ACK on the original input message.
- **Request-Reply Configuration (Optional, relevant if `request_reply_enabled: true`):**
    - `request_expiry_ms`: <int> - Default `60000`. Timeout for waiting for a reply.
    - `response_topic_prefix`: <string> - Default `"reply"`. Prefix for generated reply topics.
    - `response_topic_suffix`: <string> - Default `""`. Suffix for generated reply topics.
    - `response_queue_prefix`: <string> - Default `"reply-queue"`. Prefix for internal reply queues.
    - `user_properties_reply_topic_key`: <string> - Default `"__solace_ai_connector_broker_request_response_topic__"`. Key used in user properties for reply topic.
    - `user_properties_reply_metadata_key`: <string> - Default `"__solace_ai_connector_broker_request_reply_metadata__"`. Key used for internal RRC metadata.
    - `response_topic_insertion_expression`: <string> - Default `""`. Optional expression to insert the reply topic into the outgoing request message body.

#### Simplified App: `components` Configuration

This section is a list defining the processing logic components for the simplified app.

- `name`: <string> - Unique name for the component within this app.
- `component_module`: <string> - The Python module name where the component class is defined (e.g., `my_processor`, `llm_chat`). Required unless `component_class` is used.
- `component_class`: <string> - The fully qualified class name or a direct class reference (if using code-based app definition). Takes precedence over `component_module`. See [Simplified App Mode - Defining Apps in Code](simplified-apps.md#defining-apps-in-code-app_module).
- `component_package`: <string> - Optional. Package name to install via pip if the module is not found locally.
- `component_base_path`: <string> - Optional. Additional path to search for the `component_module`.
- `num_instances`: <int> - Optional (default 1). Scales *only this specific component* for parallel processing within the app instance.
- `disabled`: <boolean> - Optional (default `false`). If `true`, this component is skipped during flow creation.
- `component_config`: <dictionary> - Optional. Configuration specific to this component instance, passed during its initialization.
- `subscriptions`: <list> - **Required if `input_enabled` is true.** A list of dictionaries, each specifying a `topic` (using Solace wildcards `*` and `>`) that this component should process. Messages arriving on the app's `queue_name` are routed based on these subscriptions.
    - `topic`: <string> - The topic subscription string.

```yaml
    components:
      - name: main_processor
        component_module: my_processor_module
        num_instances: 2 # Run 2 instances of this processor
        component_config:
          threshold: 100
        subscriptions:
          - topic: "data/input/topic1/>"
          - topic: "data/input/topic2"
      - name: secondary_logger
        component_module: log_message
        component_config:
          log_level: "INFO"
        subscriptions:
          - topic: "audit/events/>"
```

#### App-Level Configuration (`app_config`) and Validation (`app_schema`)

Both Standard and Simplified apps support an optional `app_config:` block at the app level in the YAML configuration. This block defines key-value pairs that are accessible to all components within that app instance using `self.get_config('your_key')`. This is useful for sharing common settings like API keys, endpoints, or global thresholds.

```yaml
apps:
  - name: my_app_with_shared_config
    # ... other app settings (broker/flows) ...
    app_config:
      shared_api_key: ${GLOBAL_API_KEY}
      default_model_name: "model-x"
      processing_threshold: 0.75
    # ... components ...
```

**Validation (for Custom Apps):**

If you create a custom `App` subclass in Python (using `app_module`), you can define an `app_schema` class attribute to enable validation of the `app_config:` block. This works similarly to the `info` dictionary for components.

```python
# my_custom_app.py
from solace_ai_connector.flow.app import App

class MyValidatedApp(App):
    # Define the schema for parameters expected in the 'app_config:' block
    app_schema = {
        "config_parameters": [
            {"name": "shared_api_key", "required": True, "type": "string", "description": "API key needed by components"},
            {"name": "processing_threshold", "required": False, "type": "float", "default": 0.8, "description": "Default threshold"},
        ]
    }

    # Optional: Define default values in code (merged with YAML)
    # Note: This 'app_config' is the CLASS attribute for defining the app structure in code,
    # NOT the block validated by app_schema. The validated block comes from the YAML 'app_config:'.
    # Defaults for the validated block should be in the 'app_schema'.
    # app_config = { ... } # This defines the app structure if using code-based apps

    def __init__(self, app_info: dict, **kwargs):
        # super().__init__ handles merging and calls _validate_app_config
        super().__init__(app_info, **kwargs)
        # self.app_config (the instance attribute) is now validated and has defaults applied
        # Access validated config via self.get_config()
```

**YAML referencing the custom app:**

```yaml
apps:
  - name: validated_app_instance
    app_module: my_custom_app # Assumes my_custom_app.py exists
    app_config: # This is the block validated by MyValidatedApp.app_schema
      shared_api_key: ${MY_API_KEY} # Provided via env var or YAML
      # processing_threshold: 0.7 # Optional override
```

If `shared_api_key` is not provided in the YAML or environment variables, the connector will raise a `ValueError` during startup because it's marked as `required` in the `app_schema`. If `processing_threshold` is omitted, the default value (0.8) from the schema will be applied to the `self.app_config` dictionary within the `MyValidatedApp` instance.

**Note:** Validation only occurs for custom `App` subclasses that define a valid `app_schema` with a `config_parameters` list. Standard apps defined purely in YAML do not have their `app_config:` block validated against a schema.

#### Backward Compatibility (`flows` at top level)

For backward compatibility, if your configuration doesn't include an `apps` section but *does* include a `flows` section at the top level, the connector will automatically create a default app to contain these flows.

- If the configuration came from a single YAML file (e.g., `my_config.yaml`), the default app name will be the filename without the extension (`my_config`).
- If multiple YAML files are provided, each file containing top-level `flows` will be treated as a separate default app, named after its respective file.

Using the `apps:` structure is the recommended approach for new configurations.

### Flow Configuration (Standard Apps)

This section is used only within **Standard Apps** (those defined with a `flows:` key).

A flow is an instance of a pipeline that processes events in a sequential manner. Each `flow` is completely independent of the others and can have its own set of components and configurations.

Flows can be communicating together if programmed to do so. For example, a flow can send a message to a broker and another flow can subscribe to the same topic to receive the message.

Flows can be spread across multiple configuration files. The connector will merge the flows from all the files and run them together.

The `flows` section (within an `app` or at the top level for backward compatibility) is a list of flow configurations. Each flow configuration is a dictionary with the following keys:

- `name`: <string> - The unique name of the flow.
- `components`: A list of component configurations. Check [Component Configuration](#component-configuration) for more details.

```yaml
  flows: # Inside an app definition
  - name: <flow name>
    components:
      - component_name: <component name>
        # ... component details ...
  - name: <flow name>
    components:
      - component_name: <component name>
        # ... component details ...
```

## Message Data

Between each component in a flow, a message is passed. This message is a dictionary that is used to pass data between components within the same flow. The message object has different properties, some are available throughout the whole flow, some only between two immediate components, and some have other characteristics.

The message object has the following properties:

- `input`: The Solace broker input message. It has the following properties:
  - `payload`: The payload of the input message
  - `topic`: The topic of the input message
  - `topic_levels`: A list of the levels of the topic of the input message
  - `user_properties`: The user properties of the input message

This data type is available only after a topic subscription and then it will be available from that component onwards till overwritten by another input message.

- `user_data`: The user data object. This is a storage where the user can write and read values to be used at the different places. It is an object that is passed through the flows, and can hold any valid Python data type. To write to this object, you can use the `dest_expression` in the configuration file. To read from this object, you can use the `source_expression` in the configuration file. (This object is also available in the `evaluate_expression()` function).

- `previous`: The complete output of the previous component in the flow. This can be used to completely forward the output of the previous component as an input to the next component or be modified in the `input_transforms` section of the next component.

- Transform specific variables: Some transforms function will add specific variables to the message object that are ONLY accessible in that transform. For example, the [`map` transform](./transforms/map.md) will add `item`, `index`, and `source_list` to the message object or the [`reduce` transform](./transforms/reduce.md) will add `accumulated_value`, `current_value`, and `source_list` to the message object. You can find these details in each [transform](transforms/index.md) documentation.

## Expression Syntax

The `source_expression` and `dest_expression` values in the configuration file use a simple expression syntax to reference values in the input message and to store values in the output message. The format of the expression is:

**`<data_type>[.<qualifier>][:<index>]`**

Where:

- `data_type`: <string> - The type of data to reference. This can be one of the [message data type Check](#message-data) or one of the following:
  - message data type: input, user_data, previous, etc mentioned in the [Message Data](#message-data) section
  - `static`: A static value (e.g. `static:my_value`)
  - `template`: A template ([see more below](#templates))


- `qualifier`: <string> - The qualifier to use to reference the data. This is specific to the `data_type` and is optional. If not specified, the entire data type will be used.

- `index`: <string|int> - Where to get the data in the data type. This is optional and is specific to the `data_type`. For templates, it is the template. For other data types, it is a dot separated string or an integer index. The index will be split on dots and used to traverse the data type. If it is an integer, it will be used as an index into the data type. If it is a string, it will be used as a key to get the value from the data type.

Here are some examples of expressions:

- `input.payload:my_key` - Get the value of `my_key` from the input payload
- `user_data.my_obj:my_key` - Get the value of `my_key` from the `my_obj` object in the user data
- `static:my_value` - Use the static value `my_value`
- `user_data:my_obj2:my_list.2.my_key` - Get the value of `my_key` from the 3rd item in the `my_list` list in the `my_obj2` object in the user data

When using expressions for destination expressions, lists and objects will be created as needed. If the destination expression is a list index, the list will be extended to the index if it is not long enough. If the destination expression is an object key, the object will be created if it does not exist.

### Templates

The `template` data type is a special data type that allows you to use a template to create a value. The template is a string that can contain expressions to reference values in the input message. The format of the template is:

**`template:text text text {{template_expression}} text text text`**

Where:

- `template:` is the template data type indicator.
- `{{template_expression}}` - An expression to reference values in the input message. It has the format:

  **`<encoding>://<source_expression>`**

  Where:

  - `encoding`: <string> - The encoding/formatting to use to print out the value. This can be one of the following (Optional, defaulted to `text`):

    - `base64`: Use base64 encoding
    - `json`: Use json format
    - `yaml`: Use yaml format
    - `text`: Use string format
    - `datauri:<mime_type>`: Use data uri encoding with the specified mime type

  - `source_expression`: <string> - An expression to reference values in the input message. This has the same format as the `source_expression` in the configuration file described above.

Here is an example of a template:

```yaml
input_transforms:
  - type: copy
    source_expression: |
      template:Write me a dry joke about:
      {{text://input.payload}}

      Write the joke in the voice of {{text://input.user_properties:comedian}}

    dest_expression: user_data.llm_input:messages.0.content
  - type: copy
    source_value: user
    dest_expression: user_data.llm_input:messages.0.role
```

In this example, the `source_expression` for the first transform is a template that uses the `text` encoding to create a string.


## Component Configuration

Each component configuration (within a `flow` in a standard app, or within `components` in a simplified app) is a dictionary with the following keys:

- `component_name` / `name`: <string> - The unique name of the component within the flow/app. (`component_name` is used in standard flows, `name` is used in simplified apps).
- `component_module`: <string> - The module containing the component class (python import syntax) or the name of the [built-in component](#built-in-components). Required unless `component_class` is used.
- `component_class`: <string> - The fully qualified class name or a direct class reference. Takes precedence over `component_module`. See [Simplified App Mode - Defining Apps in Code](simplified-apps.md#defining-apps-in-code-app_module).
- `component_config`: <dictionary> - The configuration for the component. Its format is specific to the component. [Optional: if the component does not require configuration]
- `input_transforms`: <list> - A list of transforms to apply to the input message before sending it to the component. This is to ensure that the input message is in the correct format for the component. [Optional]
- `input_selection`: <dictionary> - A `source_expression` or `source_value` to use as the input to the component. Check [Expression Syntax](#expression-syntax) for more details. [Optional: If not specified, the complete previous component output (`previous`) will be used]
- `queue_depth`: <int> - The depth of the input queue for the component. [Optional, default: 5]
- `num_instances`: <int> - The number of instances of the component to run (Starts multiple threads to process messages). [Optional, default: 1]
- `subscriptions`: <list> - **Used only in Simplified Apps.** Defines topic subscriptions for routing. See [Simplified App: `components` Configuration](#simplified-app-components-configuration). [Optional]
- `broker_request_response`: <dictionary> - Configuration for the broker request-response functionality (Deprecated for components, use app-level `request_reply_enabled` in simplified apps). [Optional]

### component_module

The `component_module` is a string that specifies the module that contains the component class.

Solace-ai-connector comes with a number of flexible and highly customizable [built-in components](./components/index.md) that should cover a wide range of use cases. To use a built-in component, you can specify the name of the component in the `component_module` key and configure it using the `component_config` key. For example, to use the `aggregate` component, you would specify the following:

```yaml
- name: my_aggregator # In simplified app
  component_module: aggregate
  component_config:
    max_items: 3
    max_time_ms: 1000
```

The `component_module` can also be the python import syntax for the module. When using with a custom component, you can also use `component_base_path` to specify the base path of the python module.

Your module file should also export a variable named `info` that has the name of the class to instantiate under the key `class_name`.

For example:

```python
# src/my_custom_component.py
from solace_ai_connector.components.component_base import ComponentBase

info = {
    "class_name": "MyCustomComponent",
    # ... other info fields ...
}

class MyCustomComponent(ComponentBase):
    # ... component implementation ...
```

Configuration:
```yaml
  - name: custom_module_example
    component_base_path: . # Search relative to where connector is run
    component_module: src.my_custom_component
```

You can find an example of a custom component in the [tips and tricks](tips_and_tricks.md/#using-custom-modules-with-the-ai-connector) section.

**Note:** If you are using a custom component, you must ensure that you're using proper relative paths or your paths are in the correct level to as where you're running the connector from.

### component_class

Alternatively, especially when defining apps in code (see [Simplified App Mode - Defining Apps in Code](simplified-apps.md#defining-apps-in-code-app_module)), you can provide the component class directly.

```python
# my_app_definition.py
from solace_ai_connector.flow.app import App
from solace_ai_connector.components.component_base import ComponentBase

# Define component locally
class LocalProcessor(ComponentBase):
    info = {"class_name": "LocalProcessor", ...}
    # ... implementation ...

class MyApp(App):
    # This 'app_config' is the class attribute defining the app structure
    app_config = {
        "name": "my_code_app",
        "broker": { ... },
        "components": [
            {
                "name": "local_proc",
                "component_class": LocalProcessor, # Pass the class directly
                "component_config": { ... },
                "subscriptions": [ ... ]
            }
        ]
    }
```

If `component_class` is provided, `component_module` is ignored.

### component_config

The `component_config` is a dictionary of configuration values specific to the component. The format of this dictionary is specific to the component. You must refer to the component's documentation for the specific configuration values. for example, the [`aggregate` component](./components/aggregate.md) has the following configuration:

```yaml
  component_module: aggregate
  component_config:
    max_items: 3
    max_time_ms: 1000
```

### input_transforms

The `input_transforms` is a list of transforms to apply to the input message before sending it to the component. Each transform is a dictionary with the following keys:

- `type`: <string> - The type of transform
- `source_expression|source_value`: <string> - The source expression or static value to use as the input to the transform
- `dest_expression`: <string> - The destination expression for where to store the transformation output

The AI Event Connector comes with a number of built-in transforms that can be used to process messages. **For a list of all built-in transforms, see the [Transforms](transforms/index.md) documentation.**

Here is an example of a component configuration with input transforms:

```yaml
- name: my_transformer # In simplified app
  component_module: my_module.my_component
  component_config:
    my_key: my_value
  input_transforms:
    - type: copy
      # Extract the my_key value from the input payload
      source_expression: input.payload:my_key
      # Store the value in the newly created my_obj object in the my_keys list
      # at index 2 (i.e. my_obj.my_keys[2].my_key = input.payload.my_key)
      dest_expression: user_data.my_obj:my_keys.2.my_key
    - type: copy
      # Use a static value
      source_value: my_static_value
      # Store the value in the newly created my_obj object in the my_keys list
      # at index 3 (i.e. my_obj.my_keys[3].my_key = my_static_value)
      dest_expression: user_data.my_obj:my_keys.3.my_key
```


### input_selection

The `input_selection` is a dictionary with one (and only one) of the following keys:

- `source_expression`: <string> - An expression to use as the input to the component (see below for expression syntax)
- `source_value`: <string> - A static value to use as the input to the component.

If `input_selection` is omitted, the default behavior is `source_expression: previous`, meaning the entire output of the preceding component is used as input.

Note that, as for all values in the config file, you can use the [`invoke`](#invoke-keyword) keyword to get dynamic values

Here is an example of a component configuration with a source expression:

```yaml
- name: my_selector # In simplified app
  component_module: my_module.my_component
  component_config:
    my_key: my_value
  input_selection:
    source_expression: input.payload:my_key # Only pass my_key from the payload
```

### queue_depth

The `queue_depth` is an integer that specifies the depth of the input queue for the component. This is the number of messages that can be buffered in the queue before the component will start to block. By default, the queue depth is 5.

### num_instances

The `num_instances` is an integer that specifies the number of instances of the component to run. This is the number of threads that will be started to process messages from the input queue. By default, the number of instances is 1. In simplified apps, this scales only the specific component; in standard apps, it scales the component within its flow instance.

### subscriptions (Simplified Apps)

This key is **only used within the `components` list of a Simplified App**. It is a list of dictionaries, each defining a topic subscription for routing purposes.

- `topic`: <string> - The topic subscription string, supporting Solace wildcards (`*`, `>`).

```yaml
# Inside a simplified app's components list
- name: processor_a
  component_module: ...
  subscriptions:
    - topic: "data/typeA/>"
    - topic: "common/updates"
```

Messages arriving on the app's main queue (`broker.queue_name`) will be routed by the implicit `SubscriptionRouter` to the first component whose `subscriptions` list contains a topic matching the message's topic.

### Broker Request-Response Configuration

The `broker_request_response` configuration allows components to perform request-response operations with a broker. **This configuration at the component level is deprecated.** Use the app-level `request_reply_enabled: true` setting within the `broker:` section of a Simplified App instead.

If used, it has the following structure:

```yaml
# Deprecated - use app-level config in simplified apps
broker_request_response:
  enabled: <boolean>
  broker_config:
    # ... broker connection details ...
  request_expiry_ms: <int>
```

- `enabled`: Set to `true` to enable broker request-response functionality for the component.
- `broker_config`: Configuration for the broker connection.
- `request_expiry_ms`: Expiry time for requests in milliseconds.

For more details on using this functionality, see the [Advanced Component Features](advanced_component_features.md#broker-request-response) documentation.

### Built-in components

The AI Event Connector comes with a number of built-in components that can be used to process messages. For a list of all built-in components, see the [Components](components/index.md) documentation.

## Invoke Keyword

The `invoke` keyword is used to get dynamic values in the configuration file. An `invoke` block works by specifying an 'object' to act on with one (and only one) of the following keys:

- `module`: The name of the module to import in normal Python import syntax (e.g. `os.path`)
- `object`: An object to call a function on or get an attribute from. Note that this must have an `invoke` block itself to create the object. Objects can be nested to build up complex objects. An object is the returned value from a function call or get attribute from a module or a nested object.

It is also acceptable to specify neither `module` nor `object` if you are calling a function that is in the global namespace.

In addition to the object specifier, you can specify one (and only one) of the following keys:

- `function`: The name of the function to call on the object
- `attribute`: The name of the attribute to get from the object

In the case of a function, you can also specify a `params` key to pass parameters to the function. The params value has the following keys:

- `positional`: A list of positional parameters to pass to the function
- `keyword`: A dictionary of keyword parameters to pass to the function

`invoke` blocks can be nested to build up complex objects and call functions on them.

Here is an example of a complex `invoke` block that could be used to get AWS credentials:

```yaml
# Get AWS credentials and give it a name to reference later
shared_config: # Example usage within shared_config
  aws_credentials: &aws_credentials
    invoke:
      object:
        invoke:
          # import boto3
          module: boto3
          # Get the session object -> boto3.Session()
          function: Session
          # Passing a parameter to the Session function
          params:
            keyword:
              # Using a keyword parameter
              profile_name: default
      # Call the get_credentials function on the session object -> session.get_credentials()
      function: get_credentials

apps:
  - name: my_aws_app
    # ... other app config ...
    components:
      - name: aws_processor
        component_module: my_aws_processor
        component_config:
          aws_auth: # Pass auth details to the component
            invoke:
              # import requests_aws4auth
              module: requests_aws4auth
              # Get the AWS4Auth object -> requests_aws4auth.AWS4Auth(<params from below>)
              function: AWS4Auth
              params:
                positional:
                  # Access key
                  - invoke:
                      object: *aws_credentials # Reference shared config
                      attribute: access_key
                  # Secret key
                  - invoke:
                      object: *aws_credentials
                      attribute: secret_key
                  # Region (from environment variable)
                  - ${AWS_REGION}
                  # Service name (from environment variable)
                  - ${AWS_SERVICE}
                keyword:
                  # Pass the session token if it exists -> session_token=<session token>
                  session_token:
                    invoke:
                      object: *aws_credentials
                      attribute: token
```

**Note:** The function parameters do not support expression syntax outside of the `evaluate_expression()` function. If you need to use an expression like template, you'd have to write it to a temporary user data value and reference it in the `source_expression` function.

### Invoke with custom function

You can use invoke with your own custom functions. When using a custom functions, you can use the `path` to specify the base path of the python module.

For example, if you have a custom function in a module named `my_module` in `src` directory and the function is named `my_function`, you can use it in the configuration file like this:

```yaml
# Inside component_config or another value field
some_dynamic_value:
  invoke:
    path: .
    module: src.my_module
    function: my_function
    params:
      positional:
        - 1
        - 2
```


### invoke_functions

There is a module named `invoke_functions` that has a list of functions that can take the place of python operators used inside of `invoke`. This is useful for when you want to use an operator in a configuration file.

The following functions are available:

- `add`: param1 + param2 - can be used to add or concatenate two strings or lists
- `append`: Append the second value to the first
- `subtract`: Subtract the second number from the first
- `multiply`: Multiply two numbers together
- `divide`: Divide the first number by the second
- `modulus`: Get the modulus of the first number by the second
- `power`: Raise the first number to the power of the second
- `equal`: Check if two values are equal
- `not_equal`: Check if two values are not equal
- `greater_than`: Check if the first value is greater than the second
- `greater_than_or_equal`: Check if the first value is greater than or equal to the second
- `less_than`: Check if the first value is less than the second
- `less_than_or_equal`: Check if the first value is less than or equal to the second
- `and_op`: Check if both values are true
- `or_op`: Check if either value is true
- `not_op`: Check if the value is false
- `in_op`: Check if the first value is in the second value
- `negate`: Negate the value
- `empty_list`: Return an empty list
- `empty_dict`: Return an empty dictionary
- `empty_string`: Return an empty string
- `empty_set`: Return an empty set
- `empty_tuple`: Return an empty tuple
- `empty_float`: Return 0.0
- `empty_int`: Return 0
- `if_else`: If the first value is true, return the second value, otherwise return the third value
- `uuid`: returns a universally unique identifier (UUID)

Use positional parameters to pass values to the functions that expect arguments.

Here is an example of using the `invoke_functions` module to do some simple operations:

```yaml
# Use the invoke_functions module to do some simple operations
some_calculated_value:
  invoke:
    module: invoke_functions
    function: add
    params:
      positional:
        - 1
        - 2 # Result will be 3
```

### evaluate_expression()

If the `invoke` block is used within an area of the configuration that relates to message processing
(e.g. `input_transforms`, `component_config` values that are evaluated per message), an invoke function call can use the special function `evaluate_expression(<expression>[, type])` for any of its parameters. This function will be replaced with the value of the source expression at runtime when a message is being processed.

It is an error to use `evaluate_expression()` outside of a message processing context (e.g., directly under `shared_config`). The second parameter `type` is optional and will convert the result to the specified type. The following types are supported:

- `int`
- `float`
- `bool`
- `str`

If the value is a dict or list, the type request will be ignored

Example:

```yaml
apps:
- name: my_app
  # ...
  components:
  - name: my_calculator
    component_module: user_processor # Example using user_processor
    component_processing: # Define processing using invoke
      invoke:
        module: invoke_functions
        function: add
        params:
          positional:
            # Get value from payload, convert to int, pass as first arg
            - evaluate_expression(input.payload:my_obj.val1, int)
            # Pass static 2 as second arg
            - 2
    input_transforms: # Example usage in transforms
      - type: copy
        source_expression:
          invoke:
            module: invoke_functions
            function: multiply
            params:
              positional:
                - evaluate_expression(input.payload:quantity, int)
                - evaluate_expression(input.payload:price, float)
        dest_expression: user_data.total_cost
```

In the above example, `evaluate_expression()` is used within `component_processing` and `input_transforms` to dynamically fetch and type-convert message data during processing.

**Note:** In places where the yaml keys `source_expression` and `dest_expressions` are used, you can use the same type of expression to access a value. Check [Expression Syntax](#expression-syntax) for more details.

### user_processor Component and invoke

The `user_processor` component is a special component that allows you to define a user-defined function to process the message. This is useful for when you want to do some processing on the input message that is not possible with the built-in transforms or other components. In order to specify the user-defined function, you must define the `component_processing` property with an `invoke` block.

Here is an example of using the `user_processor` component with an `invoke` block:

```yaml
- name: my_user_processor # In simplified app
  component_module: user_processor
  component_processing:
    invoke:
      module: my_module # Your custom module
      function: my_function # Your custom function
      params:
        positional:
          # Pass data extracted from the message at runtime
          - evaluate_expression(input.payload:my_key)
          - 2 # Pass a static value
```

## Usecase Examples

You can find various usecase examples in the [examples directory](../examples/)



---

Checkout [components](./components/index.md), [transforms](./transforms/index.md), or [tips_and_tricks](tips_and_tricks.md) next.
