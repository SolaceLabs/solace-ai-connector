# Parser

Parse input from the given type to output type.

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: parser
component_config:
  input_format: <string>
  output_format: <string>
```

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| input_format | True |  | The input format of the data. Options: 'dict', 'json' 'yaml'. 'yaml' and 'json' must be string formatted. |
| output_format | True |  | The input format of the data. Options: 'dict', 'json' 'yaml'. 'yaml' and 'json' will be string formatted. |

