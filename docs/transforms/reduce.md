# ReduceTransform

This is a reduce transform where a list is iterated over. For each item, it is possible to take a value from either the source list (or anywhere else in the message) and accumulate it in the accumulator. The accumulated value will then be stored in the dest_expression.

In the accumulator function, you have access to the following keyword arguments:

 * index: The index of the current item in the source list
 * accumulated_value: The current accumulated value
 * current_value: The value of the current item in the source list
 * source_list: The source list

These should be accessed using `evaluate_expression(keyword_args:<value name>)`. For example, `evaluate_expression(keyword_args:current_value)`. See the example below for more detail.

## Configuration Parameters

```yaml
input_transforms:
  type: reduce
  source_list_expression: <string|invoke_expression>
  source_expression: <string|invoke_expression>
  accumulator_function: <invoke_expression>
  initial_value: <string|invoke_expression>
  dest_expression: <string|invoke_expression>
```

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| source_list_expression | True |  | Select the list to iterate over |
| source_expression | False |  | The field in the source list to accumulate |
| accumulator_function | True |  | The invoke expression to use to accumulate the values |
| initial_value | True |  | The initial value for the accumulator as a source_expression |
| dest_expression | True |  | The field to store the accumulated value |



## Example Configuration


```    
    input_transforms:
      - type: reduce
        source_list_expression: input.payload:my_obj.my_list
        source_expression: item.my_val
        initial_value: 0
        accumulator_function:
          invoke:
            module: invoke_functions
            function: add
              params:
                positional:
                  - evaluate_expression(keyword_args:accumulated_value)
                  - evaluate_expression(keyword_args:current_value)
        dest_expression: user_data.output:my_obj.sum
```
This transform would take a payload like this:

```
    {
      "my_obj": {
        "my_list": [
          {"my_val": 1},
          {"my_val": 2},
          {"my_val": 3}
        ],
      }
    }
```
and produce an object like this:

```
    user_data.output:
    {
      "my_obj": {
        "sum": 6
      }
    }
```
    