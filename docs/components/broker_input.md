# BrokerInput

Connect to a messaging broker and receive messages from it. The component will output the payload, topic, and user properties of the message.

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: broker_input
component_config:
  broker_type: <string>
  dev_mode: <string>
  broker_url: <string>
  broker_username: <string>
  broker_password: <string>
  broker_vpn: <string>
  reconnection_strategy: <string>
  retry_interval: <string>
  retry_count: <string>
  broker_queue_name: <string>
  temporary_queue: <string>
  broker_subscriptions: <string>
  payload_encoding: <string>
  payload_format: <string>
```

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| broker_type | False | solace | Type of broker (solace, etc.) |
| dev_mode | False | false | Operate in development mode, which just uses local queues |
| broker_url | True |  | Broker URL (e.g. tcp://localhost:55555) |
| broker_username | True |  | Client username for broker |
| broker_password | True |  | Client password for broker |
| broker_vpn | True |  | Client VPN for broker |
| reconnection_strategy | False | forever_retry | Reconnection strategy for the broker (forever_retry, parametrized_retry) |
| retry_interval | False | 10000 | Reconnection retry interval in seconds for the broker |
| retry_count | False | 10 | Number of reconnection retries. Only used if reconnection_strategy is parametrized_retry |
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
