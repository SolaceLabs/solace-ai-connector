# Assembly

Assembles messages till criteria is met, the output will be the assembled message

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: assembly
component_config:
  assemble_key: <string>
  max_items: <string>
  max_time_ms: <string>
```

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| assemble_key | True |  | The key from input message that would cluster the similar messages together |
| max_items | False | 10 | Maximum number of messages to assemble. Once this value is reached, the messages would be flushed to the output |
| max_time_ms | False | 10000 | The timeout in seconds to wait for the messages to assemble. If timeout is reached before the max size is reached, the messages would be flushed to the output |


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
    payload:     <string>,
    topic:     <string>,
    user_properties:     {
      <freeform-object>
    }
  },
  ...
]
```
| Field | Required | Description |
| --- | --- | --- |
| [].payload | False |  |
| [].topic | False |  |
| [].user_properties | False |  |
