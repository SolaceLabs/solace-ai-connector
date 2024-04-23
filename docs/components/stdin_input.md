# Stdin

STDIN input component. The component will prompt for input, which will then be placed in the message payload using the output schema below.

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: stdin_input
component_config:
```

No configuration parameters



## Component Output Schema

```
{
  text:   <string>
}
```
| Field | Required | Description |
| --- | --- | --- |
| text | True |  |
