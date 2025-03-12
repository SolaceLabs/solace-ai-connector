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
    - [Flow Configuration](#flow-configuration)
  - [Message Data](#message-data)
  - [Expression Syntax](#expression-syntax)
    - [Templates](#templates)
  - [Component Configuration](#component-configuration)
    - [component\_module](#component_module)
    - [component\_config](#component_config)
    - [input\_transforms](#input_transforms)
    - [input\_selection](#input_selection)
    - [queue\_depth](#queue_depth)
    - [num\_instances](#num_instances)
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
- `apps`: A list of app configurations, each containing flows
- `flows`: A list of flow configurations (for backward compatibility)

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

The `apps` section is a list of app configurations. Each app configuration is a dictionary with the following keys:

- `name`: <string> - The unique name of the app
- `num_instances`: <int> - The number of instances of the app to run (optional, default is 1)
- `flows`: A list of flow configurations. Check [Flow Configuration](#flow-configuration) for more details

```yaml
apps:
  - name: my_app
    num_instances: 1
    flows:
      - name: my_flow
        components:
          - component_name: my_component
  - name: another_app
    flows:
      - name: another_flow
        components:
          - component_name: another_component
```

For backward compatibility, if your configuration doesn't include an `apps` section but does include a `flows` section, the connector will automatically create an app to contain the flows in your configuration. If the configuration came from a YAML file, the app name will be the name of the file without the extension. If there are multiple files, each file will be treated as a separate app.

### Flow Configuration

A flow is an instance of a pipeline that processes events in a sequential manner. Each `flow` is completely independent of the others and can have its own set of components and configurations.

Flows can be communicating together if programmed to do so. For example, a flow can send a message to a broker and another flow can subscribe to the same topic to receive the message.

Flows can be spread across multiple configuration files. The connector will merge the flows from all the files and run them together.

The `flows` section is a list of flow configurations. Each flow configuration is a dictionary with the
following keys:

- `name`: <string> - The unique name of the flow
- `components`: A list of component configurations. Check [Component Configuration](#component-configuration) for more details

```yaml
  flows:
  - name: <flow name>
    components:
      - component_name: <component name>
  - name: <flow name>
    components:
      - component_name: <component name>
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

Each component configuration is a dictionary with the following keys:

- `component_name`: <string> - The unique name of the component within the flow.
- `component_module`: <string> - The module that contains the component class (python import syntax) or the name of the [built-in component](#built-in-components)
- `component_config`: <dictionary> - The configuration for the component. Its format is specific to the component. [Optional: if the component does not require configuration]
- `input_transforms`: <list> - A list of transforms to apply to the input message before sending it to the component. This is to ensure that the input message is in the correct format for the component. [Optional]
- `input_selection`: <dictionary> - A `source_expression` or `source_value` to use as the input to the component. Check [Expression Syntax](#expression-syntax) for more details. [Optional: If not specified, the complete previous component output will be used]
- `queue_depth`: <int> - The depth of the input queue for the component.
- `num_instances`: <int> - The number of instances of the component to run (Starts multiple threads to process messages)
- `broker_request_response`: <dictionary> - Configuration for the broker request-response functionality. [Optional]

### component_module

The `component_module` is a string that specifies the module that contains the component class.

Solace-ai-connector comes with a number of flexible and highly customizable [built-in components](./components/index.md) that should cover a wide range of use cases. To use a built-in component, you can specify the name of the component in the `component_module` key and configure it using the `component_config` key. For example, to use the `aggregate` component, you would specify the following:

```yaml
- my_component:
    component_module: aggregate
    component_config:
      max_items: 3
      max_time_ms: 1000
```

The `component_module` can also be the python import syntax for the module. When using with a custom component, you can also use `component_base_path` to specify the base path of the python module.

You're module file should also export a variable named `info` that has the name of the class to instantiate under the key `class_name`. 

For example:

```python
from solace_ai_connector.components.component_base import ComponentBase

info = {
    "class_name": "CustomClass",
}

class CustomClass(ComponentBase):
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)

    def invoke(self, _, data):
        return data["text"] + " + custom class"
```

For example, if the component class is in a module named `my_module` in `src` directory, you can use it in the configuration file like this:

```yaml
  - component_name: custom_module_example
    component_base_path: .
    component_module: src.my_module
```

You can find an example of a custom component in the [tips and tricks](tips_and_tricks.md/#using-custom-modules-with-the-ai-connector) section.

**Note:** If you are using a custom component, you must ensure that you're using proper relative paths or your paths are in the correct level to as where you're running the connector from.

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
- my_component:
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

Note that, as for all values in the config file, you can use the [`invoke`](#invoke-keyword) keyword to get dynamic values

Here is an example of a component configuration with a source expression:

```yaml
- my_component:
    component_module: my_module.my_component
    component_config:
      my_key: my_value
    input_selection:
      source_expression: input.payload:my_key
```

### queue_depth

The `queue_depth` is an integer that specifies the depth of the input queue for the component. This is the number of messages that can be buffered in the queue before the component will start to block. By default, the queue depth is 100.

### num_instances

The `num_instances` is an integer that specifies the number of instances of the component to run. This is the number of threads that will be started to process messages from the input queue. By default, the number of instances is 1.

### Broker Request-Response Configuration

The `broker_request_response` configuration allows components to perform request-response operations with a broker. It has the following structure:

```yaml
broker_request_response:
  enabled: <boolean>
  broker_config:
    dev_mode: <boolean>
    broker_url: <string>
    broker_username: <string>
    broker_password: <string>
    broker_vpn: <string>
    payload_encoding: <string>
    payload_format: <string>
  request_expiry_ms: <int>
```

- `enabled`: Set to `true` to enable broker request-response functionality for the component.
- `broker_config`: Configuration for the broker connection.
  - `broker_type`: Type of the broker (e.g., "solace").
  - `broker_url`: URL of the broker.
  - `broker_username`: Username for broker authentication.
  - `broker_password`: Password for broker authentication.
  - `broker_vpn`: VPN name for the broker connection.
  - `payload_encoding`: Encoding for the payload (e.g., "utf-8", "base64").
  - `payload_format`: Format of the payload (e.g., "json", "text").
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
- aws_credentials: &aws_credentials
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

- aws_4_auth:
    invoke:
      # import requests_aws4auth
      module: requests_aws4auth
      # Get the AWS4Auth object -> requests_aws4auth.AWS4Auth(<params from below>)
      function: AWS4Auth
      params:
        positional:
          # Access key
          - invoke:
              object: *aws_credentials
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
- my_custom_function:
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
- simple_operations:
    invoke:
      module: invoke_functions
      function: add
      params:
        positional:
          - 1
          - 2
```

### evaluate_expression()

If the `invoke` block is used within an area of the configuration that relates to message processing
(e.g. input_transforms), an invoke function call can use the special function `evaluate_expression(<expression>[, type])` for any of its parameters. This function will be replaced with the value of the source expression at runtime.

It is an error to use `evaluate_expression()` outside of a message processing. The second parameter is optional
and will convert the result to the specified type. The following types are supported:

- `int`
- `float`
- `bool`
- `str`

If the value is a dict or list, the type request will be ignored

Example:

```yaml
- flows:
  - my_flow:
    - my_component:
      input_transforms:
        -type: copy
         source_expression:
            invoke:
              module: invoke_functions
              function: add
              params:
                positional:
                  - evaluate_expression(input.payload:my_obj.val1, int)
                  - 2
         dest_expression: user_data.my_obj:result
```

In the above example, the `evaluate_expression()` function is used to get the value of `input.payload:my_obj.val1`,
convert it to an `int` and add 2 to it.

**Note:** In places where the yaml keys `source_expression` and `dest_expressions` are used, you can use the same type of expression to access a value. Check [Expression Syntax](#expression-syntax) for more details.

### user_processor Component and invoke

The `user_processor` component is a special component that allows you to define a user-defined function to process the message. This is useful for when you want to do some processing on the input message that is not possible with the built-in transforms or other components. In order to specify the user-defined function, you must define the `component_processing` property with an `invoke` block.

Here is an example of using the `user_processor` component with an `invoke` block:

```yaml
- my_user_processor:
    component_name: my_user_processor
    component_module: user_processor
    component_processing:
      invoke:
        module: my_module
        function: my_function
        params:
          positional:
            - evaluate_expression(input.payload:my_key)
            - 2
```

## Usecase Examples

You can find various usecase examples in the [examples directory](../examples/)



---

Checkout [components](./components/index.md), [transforms](./transforms/index.md), or [tips_and_tricks](tips_and_tricks.md) next.
