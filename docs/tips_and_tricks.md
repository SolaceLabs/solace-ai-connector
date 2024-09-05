# Some tips and tricks for using the Solace AI Connector

- [Some tips and tricks for using the Solace AI Connector](#some-tips-and-tricks-for-using-the-solace-ai-connector)
  - [Using `user_data` as temporary storage](#using-user_data-as-temporary-storage)
  - [Using custom modules with the AI Connector](#using-custom-modules-with-the-ai-connector)


## Using `user_data` as temporary storage

Some times you might need to chain multiple transforms together, but transforms do not support nesting. For example if you'd want to `map` through a list of strings first and then reduce them to a single string, you can write your transforms sequentially and write to a temporary place in `user_data` like `user_data.temp`:

For example:
    
```yaml
        input_transforms:
          # Transform each response to use the template
          - type: map
            source_list_expression: previous
            source_expression: |
              template:<response-{{text://index}}>
              {{text://item:content}}
              </response-{{text://index}}>\n
            dest_list_expression: user_data.temp:responses # Temporary storage

          # Transform and reduce the responses to one message
          - type: reduce
            source_list_expression: user_data.temp:responses # Using the value in temporary storage
            source_expression: item
            initial_value: ""
            accumulator_function:
              invoke:
                module: invoke_functions
                function: add
                params:
                  positional:
                    - evaluate_expression(keyword_args:accumulated_value)
                    - evaluate_expression(keyword_args:current_value)
            dest_expression: user_data.output:responses # Value to be used in the component

        input_selection:
          source_expression: user_data.output
```

## Using custom modules with the AI Connector

This is a simple example that utilizes a custom component, a class based transform and a function based transform.

First follow the following steps to create a repository to run the ai connector:

```bash
mkdir -p module-example/src
cd module-example
python3 -m venv env
source env/bin/activate
pip install solace-ai-connector
touch config.yaml src/custom_component.py src/custom_function.py src/__init__.py
```

Write the following code to `src/custom_function.py`:

```python
def custom_function(input_data):
    return input_data + " + custom function value"

class CustomFunctionClass:    
    def get_custom_value(self, input_data):
        return input_data + " + custom function class"
```

Write the following code to `src/custom_component.py`:

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

Write the following config to `config.yaml`:

```yaml
log:
  stdout_log_level: INFO
  log_file_level: INFO
  log_file: solace_ai_connector.log

flows:
  - name: custom_module_flow
    components:
      # Input from a standard in
      - component_name: stdin
        component_module: stdin_input

    # Using Custom component
      - component_name: custom_component_example
        component_base_path: .
        component_module: src.custom_component
        input_selection:
          source_expression: previous

     # Output to a standard out
      - component_name: stdout
        component_module: stdout_output
        # Using custom transforms
        input_transforms:
        # Instantiating a class and calling its function
          - type: copy
            source_expression:
                invoke:
                    # Creating an object of the class
                    object:
                        invoke:
                          path: .
                          module: src.custom_function
                          function: CustomFunctionClass
                    # Calling the function of the class
                    function: get_custom_value
                    params:
                        positional:
                            - source_expression(previous)
            dest_expression: user_data.output:class
            # Calling a function directly
          - type: copy
            source_expression:
                invoke:
                    module: src.custom_function
                    function: custom_function
                    params:
                        positional:
                            - source_expression(previous)
            dest_expression: user_data.output:function
        component_input:
          source_expression: user_data.output
```

Then run the AI connector with the following command:

```bash
solace-ai-connector config.yaml
```

---

Find more examples in the [examples](../examples/) directory.
