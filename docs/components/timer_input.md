# TimerInput

An input that will generate a message at a specified interval.

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: timer_input
component_config:
  interval_ms: <string>
  skip_messages_if_behind: <boolean>
```

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| interval_ms | False |  | The interval in milliseconds at which to generate a message. |
| skip_messages_if_behind | False | False | If false, when the component is blocked for some time, it will catch up by generating multiple messages in quick succession. If true, then the component will always wait at least the interval time before generating the next message. Note that due to some messages in the pipeline, there will always be a couple of quick messages generated. |



## Component Output Schema

```
<None>
```
