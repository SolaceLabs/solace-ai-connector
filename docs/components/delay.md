# Delay

A simple component that simply passes the input to the output, but with a configurable delay. Note that it will not service the next input until the delay has passed. If this component has num_instances > 1, each instance will run in parallel. 

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: delay
component_config:
  delay: <number>
```

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| delay | False | 1 | The delay in seconds |


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
