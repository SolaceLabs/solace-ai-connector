# BrokerInput

Connect to a messaging broker and receive messages from it. The component will output the payload, topic, and user properties of the message.

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: broker_input
component_config:
  broker_queue_name: <string>
  temporary_queue: <string>
  broker_subscriptions: <string>
  payload_encoding: <string>
  payload_format: <string>
```

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| broker_queue_name | False |  | Queue name for broker, if not provided it will use a temporary queue |
| temporary_queue | False | False | Whether to create a temporary queue that will be deleted after disconnection, defaulted to True if broker_queue_name is not provided |
| broker_subscriptions | True |  | Subscriptions for broker |
| payload_encoding | False | utf-8 | Encoding for the payload (utf-8, base64, gzip, none) |
| payload_format | False | json | Format for the payload (json, yaml, text) |



## Component Output Schema

```
{
  payload:   <string>,
  topic:   <string>,
  user_properties:   {
    <freeform-object>
  }
}
```
| Field | Required | Description |
| --- | --- | --- |
| payload | True |  |
| topic | True |  |
| user_properties | True |  |
