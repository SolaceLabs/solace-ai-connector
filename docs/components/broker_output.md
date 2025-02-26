# BrokerOutput

Connect to a messaging broker and send messages to it. Note that this component requires that the data is transformed into the input schema.

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: broker_output
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
  payload_encoding: <string>
  payload_format: <string>
  propagate_acknowledgements: <string>
  copy_user_properties: <string>
  decrement_ttl: <string>
  discard_on_ttl_expiration: <string>
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
| payload_encoding | False | utf-8 | Encoding for the payload (utf-8, base64, gzip, none) |
| payload_format | False | json | Format for the payload (json, yaml, text) |
| propagate_acknowledgements | False | True | Propagate acknowledgements from the broker to the previous components |
| copy_user_properties | False | False | Copy user properties from the input message |
| decrement_ttl | False |  | If present, decrement the user_properties.ttl by 1 |
| discard_on_ttl_expiration | False | False | If present, discard the message when the user_properties.ttl is 0 |


## Component Input Schema

```
{
  payload:   <any>,
  topic:   <string>,
  user_properties:   {
    <freeform-object>
  }
}
```
| Field | Required | Description |
| --- | --- | --- |
| payload | True | Payload of the message sent to the broker |
| topic | True | Topic to send the message to |
| user_properties | False | User properties to send with the message |
