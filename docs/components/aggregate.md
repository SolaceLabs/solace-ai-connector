# Aggregate

Take multiple messages and aggregate them into one. The output of this component is a list of the exact structure of the input data.

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: aggregate
component_config:
  max_items: <integer>
  max_time_ms: <integer>
```

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| max_items | False | 10 | Number of input messages to aggregate before sending an output message |
| max_time_ms | False | 1000 | Number of milliseconds to wait before sending an output message |


## Component Input Schema

```
{
  <freeform-object>
}
```


## Component Output Schema

```
[
  {
    <freeform-object>
  },
  ...
]
```
