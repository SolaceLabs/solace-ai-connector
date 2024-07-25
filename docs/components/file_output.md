# FileOutput

File output component

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: file_output
component_config:
```

No configuration parameters


## Component Input Schema

```
{
  content:   <string>,
  file_path:   <string>,
  mode:   <string>
}
```
| Field | Required | Description |
| --- | --- | --- |
| content | True |  |
| file_path | True | The path to the file to write to |
| mode | False | The mode to open the file in: w (write), a (append). Default is w. |
