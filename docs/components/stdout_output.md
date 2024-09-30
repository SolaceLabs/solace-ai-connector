# Stdout

STDOUT output component

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: stdout_output
component_config:
  add_new_line_between_messages: <boolean>
```

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| add_new_line_between_messages | False | True | Add a new line between messages |


## Component Input Schema

```
{
  text:   <string>
}
```
| Field | Required | Description |
| --- | --- | --- |
| text | True |  |
