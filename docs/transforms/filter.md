# FilterTransform

This is a filter transform where a list is iterated over. For each item, the provided filter_functions is run. If it evaluates to True then the item is copied to the destination list. If it evaluates to False then the item is not copied to the destination list.

In the filter function, you have access to the following keyword arguments:

 * index: The index of the current item in the source list
 * current_value: The value of the current item in the source list
 * source_list: The source list

These should be accessed using `evaluate_expression(keyword_args:<value name>)`. For example, `evaluate_expression(keyword_args:current_value)`. See the example below for more detail.

## Configuration Parameters

```yaml
input_transforms:
  type: filter
  source_list_expression: <string|invoke_expression>
  source_expression: <string|invoke_expression>
  filter_function: <invoke_expression>
  dest_list_expression: <string|invoke_expression>
  dest_expression: <string|invoke_expression>
```

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| source_list_expression | True |  | Select the list to iterate over |
| source_expression | False |  | The field in the source list to accumulate |
| filter_function | True |  | The invoke function to use to filter the list |
| dest_list_expression | True |  | The list to copy the item into |
| dest_expression | False |  | The field within the dest list to copy the item into |



## Example Configuration


```    
    input_transforms:
      - type: filter
        source_list_expression: input.payload:my_obj.my_list
        source_expression: item
        filter_function:
          invoke:
            module: invoke_functions
            function: greater_than
              params:
                positional:
                  - evaluate_expression(keyword_args:current_value.my_val)
                  - 2
        dest_expression: user_data.output:new_list
```
This transform would take a payload like this:

```
    {
      "my_obj": {
        "my_list": [
          {"my_val": 1},
          {"my_val": 2},
          {"my_val": 3},
          {"my_val": 4}
        ],
      }
    }
```
and produce an object like this:

```
    user_data.output:
    {
        new_list: [
          {"my_val": 3},
          {"my_val": 4}
        ],
    }
```
