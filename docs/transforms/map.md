# MapTransform

This is a map transform where a list is iterated over. For each item, it is possible to take a value from either the source list (or anywhere else in the message), optionally process it and then put it in the same index in the destination list. If the destination list is shorter than the source list, the destination list will be extended to match the length of the source list. In the processing function, you have access to the following keyword arguments:

 * index: The index of the current item in the source list
 * current_value: The value of the current item in the source list
 * source_list: The source list

These should be accessed using `evaluate_expression(keyword_args:<value name>)`. For example, `evaluate_expression(keyword_args:current_value)`. See the example below for more detail.

## Configuration Parameters

```yaml
input_transforms:
  type: map
  source_list_expression: <string|invoke_expression>
  source_expression: <string|invoke_expression>
  processing_function: <invoke_expression>
  dest_list_expression: <string|invoke_expression>
  dest_expression: <string|invoke_expression>
```

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| source_list_expression | True |  | Select the list to copy from |
| source_expression | True |  | A field to copy. All normal source_expression options are available, allowing you to use the source list as the iterator, but copy the same value from elsewhere in the message over and over. Also, two other expression datatypes are available: 'item' and 'index'. 'item' allows you to select from the source list entry itself (e.g. item:field_name). 'index' allows you to select the index of the source list. |
| processing_function | False |  | An optional invoke function to process the source data before it is placed in the destination list |
| dest_list_expression | True |  | The list to copy the item into |
| dest_expression | False |  | The field within the dest list to copy the item into |



## Example Configuration


```    
    input_transforms:
      - type: map
        source_list_expression: input.payload:my_obj.my_list
        source_expression: item.my_val
        processing_function:
          invoke:
            module: invoke_functions
            function: add
              params:
                positional:
                  - evaluate_expression(keyword_args:current_value)
                  - 2
        dest_list_expression: user_data.output:new_list
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
        new_list: [3, 4, 5]
    }
```
