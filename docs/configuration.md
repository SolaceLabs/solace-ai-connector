# Configuration for the AI Event Connector

The AI Event Connector is highly configurable. You can define the components of each flow, the queue depths between them, and the number of instances of each component. The configuration is done through a YAML file that is loaded when the connector starts. This allows you to easily change the configuration without having to modify the code.

## Configuration File Format and Rules

The configuration file is a YAML file that is loaded when the connector starts. 

### Special values

Within the configuration, you can have simple static values, environment variables, or dynamic values using the `invoke` keyword.

#### Environment Variables

You can use environment variables in the configuration file by using the `${}` syntax. For example, if you have an environment variable `MY_VAR` you can use it in the configuration file like this:

```yaml
my_key: ${MY_VAR}
```

#### Dynamic Values (invoke keyword)

You can use dynamic values in the configuration file by using the `invoke` keyword. This allows you to do such things as import a module, instantiate a class and call a function to get the value. For example, if you want to get the operating system type you can use it in the configuration file like this:

```yaml
os_type: 
  invoke:
    module: platform
    function: system
```

An `invoke` block works by specifying an 'object' to act on with one (and only one) of the following keys:
- `module`: The name of the module to import in normal Python import syntax  (e.g. `os.path`)
- `object`: An object to call a function on or get an attribute from. Note that this must have an `invoke` block itself to create the object. Objects can be nested to build up complex objects. An object is the returned value from a function call or attribute get from a module or a nested object.

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

##### invoke_functions

There is a module named `invoke_functions` that has a list of functions that can take the place of python operators. This is useful for when you want to use an operator in a configuration file. The following functions are available:
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

##### source_expression()

If the `invoke` block is used within an area of the configuration that relates to message processing 
(e.g. input_transforms), an invoke function call can use the special function `source_expression(<expression>[, type])` for 
any of its parameters. This function will be replaced with the value of the source expression at runtime.
It is an error to use `source_expression()` outside of a message processing. The second parameter is optional
and will convert the result to the specified type. The following types are supported:
- `int`
- `float`
- `bool`
- `str`
If the value is a dict or list, the type request will be ignored

Example:
```yaml
-flows:
  -my_flow:
    -my_component:
      input_transforms:
        -type: copy
         source_expression: 
            invoke:
              module: invoke_functions
              function: add
              params:
                positional:
                  - source_expression(input.payload:my_obj.val1, int)
                  - 2
         dest_expression: user_data.my_obj:result
```

In the above example, the `source_expression()` function is used to get the value of `input.payload:my_obj.val1`,
convert it to an `int` and add 2 to it.

**Note:** In places where the yaml keys `source_expression` and `dest_expressions` are used, you can use the same type of expression to access a value. Check [Expression Syntax](#expression-syntax) for more details.

##### user_processor component and invoke

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
              - source_expression(input.payload:my_key)
              - 2
```





## Configuration File Structure

The configuration file is a YAML file with these top-level keys:

- `log`: Configuration of logging for the connector
- `shared_config`: Named configurations that can be used by multiple components later in the file
- `flows`: A list of flow configurations. 

### Log Configuration

The `log` configuration section is used to configure the logging for the connector. It configures the logging behaviour for stdout and file logs. It has the following keys:

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

### Flow Configuration

The `flows` section is a list of flow configurations. Each flow configuration is a dictionary with the
following keys:
- `name`: <string> - The unique name of the flow
- `components`: A list of component configurations

#### Component Configuration

Each component configuration is a dictionary with the following keys:
- `component_name`: <string> - The unique name of the component within the flow
- `component_module`: <string> - The module that contains the component class (python import syntax)
- `component_config`: <dictionary> - The configuration for the component. Its format is specific to the component
- `input_transforms`: <list> - A list of transforms to apply to the input message before sending it to the component
- `component_input`: <dictionary> - A source_expression or source_value to use as the input to the component. 
- `queue_depth`: <int> - The depth of the input queue for the component
- `num_instances`: <int> - The number of instances of the component to run

**Note: For a list of all built-in components, see the [Components](components/index.md) documentation.**

##### component_config

The `component_config` is a dictionary of configuration values specific to the component. The format of this dictionary is specific to the component. You must refer to the component's documentation for the specific configuration values.

##### input_transforms

The `input_transforms` is a list of transforms to apply to the input message before sending it to the component. Each transform is a dictionary with the following keys:
- `type`: <string> - The type of transform
- `source_expression|source_value`: <string> - The source expression or value to use as the input to the transform
- `dest_expression`: <string> - The destination expression for where to store the transformation output

For a list of all available transform functions check [Transforms](transforms/index.md) page.

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
```

###### Built-in Transforms

The AI Event Connector comes with a number of built-in transforms that can be used to process messages. For a list of all built-in transforms, see the [Transforms](transforms/index.md) documentation.

##### component_input

The `component_input` is a dictionary with one (and only one) of the following keys:
- `source_expression`: <string> - An expression to use as the input to the component (see below for expression syntax)
- `source_value`: <string> - A value to use as the input to the component. 

Note that, as for all values in the config file, you can use the `invoke` keyword to get dynamic values

Here is an example of a component configuration with a source expression:

```yaml
  - my_component:
      component_module: my_module.my_component
      component_config:
        my_key: my_value
      component_input:
        source_expression: input.payload:my_key
```

##### queue_depth

The `queue_depth` is an integer that specifies the depth of the input queue for the component. This is the number of messages that can be buffered in the queue before the component will start to block. By default, the queue depth is 100.


##### num_instances

The `num_instances` is an integer that specifies the number of instances of the component to run. This is the number of threads that will be started to process messages from the input queue. By default, the number of instances is 1.

#### Built-in components

The AI Event Connector comes with a number of built-in components that can be used to process messages. For a list of all built-in components, see the [Components](components/index.md) documentation.

### Expression Syntax

The `source_expression` and `dest_expression` values in the configuration file use a simple expression syntax to reference values in the input message and to store values in the output message. The format of the expression is:

`<data_type>[.<qualifier>][:<index>]`

Where:

- `data_type`: <string> - The type of data to reference. This can be one of the following:
  - `input`: The input message. It supports the qualifiers:
    - `payload`: The payload of the input message
    - `topic`: The topic of the input message
    - `topic_levels`: A list of the levels of the topic of the input message
    - `user_properties`: The user properties of the input message
  - `user_data`: The user data object. The qualifier is required to specify the name of the user data object. `user_data` is an object that is passed through the flows, where the user can read and write values to it to be accessed at the different places.
  - `static`: A static value (e.g. `static:my_value`)
  - `template`: A template ([see more below](#templates))
  - `previous`: The output from the previous component in the flow. This could be of any type depending on the previous component

- `qualifier`: <string> - The qualifier to use to reference the data. This is specific to the `data_type` and is optional. If not specified, the entire data type will be used.

- `index`: <string|int> - Where to get the data in the data type. This is optional and is specific to the `data_type`. For templates, it is the template. For other data types, it is a dot separated string or an integer index. The index will be split on dots and used to traverse the data type. If it is an integer, it will be used as an index into the data type. If it is a string, it will be used as a key to get the value from the data type.

Here are some examples of expressions:

- `input.payload:my_key` - Get the value of `my_key` from the input payload
- `user_data.my_obj:my_key` - Get the value of `my_key` from the `my_obj` object in the user data
- `static:my_value` - Use the static value `my_value`
- `user_data:my_obj2:my_list.2.my_key` - Get the value of `my_key` from the 3rd item in the `my_list` list in the `my_obj2` object in the user data

When using expressions for destination expressions, lists and objects will be created as needed. If the destination expression is a list index, the list will be extended to the index if it is not long enough. If the destination expression is an object key, the object will be created if it does not exist.

#### Templates

The `template` data type is a special data type that allows you to use a template to create a value. The template is a string that can contain expressions to reference values in the input message. The format of the template is:

`template:text text text {{template_expression}} text text text`

Where:

- `template:` is the template data type indicator.
- `{{template_expression}}` - An expression to reference values in the input message. It has the format:

  `<encoding>://<source_expression>`

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
