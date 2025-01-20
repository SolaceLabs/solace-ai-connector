# BrokerOutput

Connect to a messaging broker and send messages to it. Note that this component requires that the data is transformed into the input schema.

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: broker_output
component_config:
  payload_encoding: <string>
  payload_format: <string>
  propagate_acknowledgements: <string>
  copy_user_properties: <string>
  decrement_ttl: <string>
  discard_on_ttl_expiration: <string>
```

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
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
