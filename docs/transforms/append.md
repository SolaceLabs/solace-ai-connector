# AppendTransform

Select a source value and append it to a destination list. 

## Configuration Parameters

```yaml
input_transforms:
  type: append
  source_expression: <string|invoke_expression>
  dest_expression: <string|invoke_expression>
```

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| source_expression | True |  | The field to append to the destination list. |
| dest_expression | True |  | The field to append the source value to. |

