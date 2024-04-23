# MessageFilter

A filtering component. This will apply a user configurable expression. If the expression evaluates to True, the message will be passed on. If the expression evaluates to False, the message will be discarded. If the message is discarded, any previous components that require an acknowledgement will be acknowledged.

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: message_filter
component_config:
  filter_expression: <string>
```

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| filter_expression | True |  | A dynmaic invoke configuration that will return true if message should be passed or false to drop it |


## Component Input Schema

```
{
  <freeform-object>
}
```


## Component Output Schema

```
{
  <freeform-object>
}
```
