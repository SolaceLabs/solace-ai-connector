# CopyTransform

Copy Transform - copy a value from one field to another.

## Configuration Parameters

```yaml
input_transforms:
  type: copy
  source_expression: <string|invoke_expression>
  dest_expression: <string|invoke_expression>
```

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| source_expression | True |  | The field to copy from. |
| dest_expression | True |  | The field to copy the source value to. |

