# Stdin

STDIN input component. The component will prompt for input, which will then be placed in the message payload using the output schema below. The component will wait for its output message to be acknowledged before prompting for the next input.

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: stdin_input
component_config:
  prompt: <string>
```

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| prompt | False |  | The prompt to display when asking for input |



## Component Output Schema

```
{
  text:   <string>
}
```
| Field | Required | Description |
| --- | --- | --- |
| text | True |  |
